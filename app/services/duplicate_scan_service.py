"""Read-only full-library duplicate scans and cleanup-plan previews."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.constants import DEFAULT_PHASH_THRESHOLD, SUPPORTED_FORMATS
from app.database.models import Wallpaper
from app.utils.hashing import compute_phash
from app.utils.image_utils import validate_image_file

logger = logging.getLogger(__name__)

MAX_PHASH_DISTANCE = 64
_HASH_CHUNK_SIZE = 1024 * 1024
_SCAN_PAGE_SIZE = 250


@dataclass(frozen=True)
class FileIdentity:
    """Filesystem identity captured around a read-only file inspection."""

    canonical_path: str
    device: int
    inode: int
    size_bytes: int
    modified_ns: int
    changed_ns: int


@dataclass(frozen=True)
class DuplicateCandidate:
    """A library record verified against its current on-disk image."""

    wallpaper: Wallpaper
    canonical_path: Path
    sha256: str
    phash: str
    size_bytes: int
    width: int
    height: int
    image_format: str
    identity: FileIdentity

    @property
    def wallpaper_id(self) -> int:
        if self.wallpaper.id is None:
            raise ValueError("A scanned wallpaper must have a database ID.")
        return self.wallpaper.id

    @property
    def display_name(self) -> str:
        return self.wallpaper.filename or self.canonical_path.name


@dataclass(frozen=True)
class SimilarityEdge:
    """A direct pHash relationship between two files in a near group."""

    first_id: int
    second_id: int
    hamming_distance: int
    similarity_percent: float


@dataclass(frozen=True)
class DuplicateGroup:
    """A deterministic exact-hash group or connected near-match group."""

    group_id: str
    kind: Literal["exact", "near"]
    members: tuple[DuplicateCandidate, ...]
    edges: tuple[SimilarityEdge, ...] = ()

    @property
    def highest_similarity(self) -> float:
        if self.kind == "exact":
            return 100.0
        return max((edge.similarity_percent for edge in self.edges), default=0.0)

    @property
    def exact_redundant_bytes(self) -> int:
        if self.kind != "exact" or not self.members:
            return 0
        return sum(member.size_bytes for member in self.members[1:])


@dataclass(frozen=True)
class ScanIssue:
    """A safe-to-display scan issue that does not include an absolute path."""

    wallpaper_id: int | None
    filename: str
    code: str
    message: str


@dataclass(frozen=True)
class DuplicateScanReport:
    """In-memory result of one completed or cancelled scan."""

    threshold: int
    total_records: int
    scanned_records: int
    candidates: tuple[DuplicateCandidate, ...]
    groups: tuple[DuplicateGroup, ...]
    issues: tuple[ScanIssue, ...]
    started_at: str
    finished_at: str
    completed: bool
    cancelled: bool

    @property
    def exact_groups(self) -> tuple[DuplicateGroup, ...]:
        return tuple(group for group in self.groups if group.kind == "exact")

    @property
    def near_groups(self) -> tuple[DuplicateGroup, ...]:
        return tuple(group for group in self.groups if group.kind == "near")

    @property
    def candidate_count(self) -> int:
        return len({member.wallpaper_id for group in self.groups for member in group.members})

    @property
    def exact_redundant_bytes_estimate(self) -> int:
        """Conservative estimate based only on byte-identical exact groups."""
        return sum(group.exact_redundant_bytes for group in self.exact_groups)


@dataclass(frozen=True)
class CleanupPreviewEntry:
    group_id: str
    retained: DuplicateCandidate
    selected_for_removal: tuple[DuplicateCandidate, ...]


@dataclass(frozen=True)
class CleanupPreview:
    """Read-only preview; it intentionally exposes no file-operation method."""

    entries: tuple[CleanupPreviewEntry, ...]
    files_selected: int
    estimated_bytes: int


class CleanupPreviewError(ValueError):
    """The proposed preview is unsafe or no longer matches scan-time state."""


ProgressCallback = Callable[[int, int, str], None]


class ScanCancelledError(Exception):
    """Internal signal used to stop hashing and file comparisons promptly."""


class InvalidImageError(ValueError):
    """An unsupported, corrupt, or undecodable file in the library."""


def validate_threshold(value: int) -> int:
    """Validate a 64-bit pHash Hamming-distance threshold."""
    if type(value) is not int or not 0 <= value <= MAX_PHASH_DISTANCE:
        raise ValueError(f"pHash distance must be between 0 and {MAX_PHASH_DISTANCE}.")
    return value


def _identity_from_stat(path: Path, info: os.stat_result) -> FileIdentity:
    """Build an identity from an os.stat_result without retaining file handles."""
    return FileIdentity(
        canonical_path=str(path),
        device=info.st_dev,
        inode=info.st_ino,
        size_bytes=info.st_size,
        modified_ns=info.st_mtime_ns,
        changed_ns=info.st_ctime_ns,
    )


def _file_identity(path: Path) -> FileIdentity:
    canonical = path.resolve(strict=True)
    info = canonical.stat()
    if not canonical.is_file():
        raise OSError("Not a regular file.")
    return _identity_from_stat(canonical, info)


def _open_handle_matches_path(opened: FileIdentity, expected: FileIdentity) -> bool:
    """Compare stable handle metadata; Windows reports ctime differently for fstat."""
    return (
        opened.canonical_path == expected.canonical_path
        and opened.device == expected.device
        and opened.inode == expected.inode
        and opened.size_bytes == expected.size_bytes
        and opened.modified_ns == expected.modified_ns
    )


def _check_cancelled(cancel_event: threading.Event) -> None:
    if cancel_event.is_set():
        raise ScanCancelledError


def _hash_file(path: Path, expected_identity: FileIdentity, cancel_event: threading.Event) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as image_file:
        opened_identity = _identity_from_stat(path, os.fstat(image_file.fileno()))
        if not _open_handle_matches_path(opened_identity, expected_identity):
            raise OSError("File changed before hashing.")
        while True:
            _check_cancelled(cancel_event)
            chunk = image_file.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        final_open_identity = _identity_from_stat(path, os.fstat(image_file.fileno()))
        if not _open_handle_matches_path(final_open_identity, expected_identity):
            raise OSError("File changed during hashing.")
    if _file_identity(path) != expected_identity:
        raise OSError("File changed during hashing.")
    return digest.hexdigest()


def _same_bytes(
    first: DuplicateCandidate,
    second: DuplicateCandidate,
    cancel_event: threading.Event,
) -> bool:
    """Compare complete file contents in bounded memory."""
    if first.size_bytes != second.size_bytes:
        return False
    if _file_identity(first.canonical_path) != first.identity:
        raise OSError("File changed since it was hashed.")
    if _file_identity(second.canonical_path) != second.identity:
        raise OSError("File changed since it was hashed.")

    with first.canonical_path.open("rb") as first_file, second.canonical_path.open("rb") as second_file:
        while True:
            _check_cancelled(cancel_event)
            first_chunk = first_file.read(_HASH_CHUNK_SIZE)
            second_chunk = second_file.read(_HASH_CHUNK_SIZE)
            if first_chunk != second_chunk:
                return False
            if not first_chunk:
                break

    if _file_identity(first.canonical_path) != first.identity:
        raise OSError("File changed during byte comparison.")
    if _file_identity(second.canonical_path) != second.identity:
        raise OSError("File changed during byte comparison.")
    return True


def _similarity(distance: int) -> float:
    return round((MAX_PHASH_DISTANCE - distance) * 100 / MAX_PHASH_DISTANCE, 2)


class _BKNode:
    def __init__(self, value: int, index: int) -> None:
        self.value = value
        self.indices = [index]
        self.children: dict[int, _BKNode] = {}


class _BKTree:
    """BK-tree candidate index for exact Hamming-radius pHash queries."""

    def __init__(self) -> None:
        self._root: _BKNode | None = None

    def add(self, value: int, index: int) -> None:
        if self._root is None:
            self._root = _BKNode(value, index)
            return
        node = self._root
        while True:
            distance = (value ^ node.value).bit_count()
            if distance == 0:
                node.indices.append(index)
                return
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = _BKNode(value, index)
                return
            node = child

    def query(self, value: int, radius: int) -> list[tuple[int, int]]:
        matches: list[tuple[int, int]] = []
        if self._root is None:
            return matches
        pending = [self._root]
        while pending:
            node = pending.pop()
            distance = (value ^ node.value).bit_count()
            if distance <= radius:
                matches.extend((index, distance) for index in node.indices)
            lower = max(0, distance - radius)
            upper = distance + radius
            pending.extend(
                child for edge, child in node.children.items() if lower <= edge <= upper
            )
        return matches


class DuplicateScanService:
    """Compute exact and near groups from a snapshot of indexed records.

    Indexed SHA/pHash metadata is deliberately recomputed from the current
    files, so stale database hashes cannot create a false group.
    """

    def __init__(
        self,
        wallpapers: Sequence[Wallpaper],
        threshold: int = DEFAULT_PHASH_THRESHOLD,
    ) -> None:
        self._wallpapers = tuple(wallpapers)
        self._threshold = validate_threshold(threshold)

    def scan(
        self,
        cancel_event: threading.Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> DuplicateScanReport:
        cancel = cancel_event or threading.Event()
        callback = progress or (lambda _done, _total, _name: None)
        started_at = datetime.now(UTC).isoformat()
        issues: list[ScanIssue] = []
        candidates: list[DuplicateCandidate] = []
        scanned = 0
        seen_paths: dict[str, int | None] = {}

        for wallpaper in self._wallpapers:
            if cancel.is_set():
                return self._report(
                    candidates, (), issues, scanned, started_at, completed=False, cancelled=True
                )
            try:
                candidate = self._scan_one(wallpaper, cancel)
            except ScanCancelledError:
                return self._report(
                    candidates, (), issues, scanned, started_at, completed=False, cancelled=True
                )
            except FileNotFoundError:
                candidate = None
                issues.append(self._issue(wallpaper, "missing", "File is missing."))
            except PermissionError:
                candidate = None
                issues.append(self._issue(wallpaper, "unreadable", "File cannot be read."))
            except InvalidImageError:
                candidate = None
                issues.append(self._issue(wallpaper, "invalid", "File is unsupported, corrupt, or not a readable image."))
            except (OSError, ValueError):
                candidate = None
                issues.append(self._issue(wallpaper, "changed", "File changed or became unavailable during scanning."))
            except Exception as exc:
                candidate = None
                logger.debug("Duplicate scan skipped one image (%s).", type(exc).__name__)
                issues.append(self._issue(wallpaper, "invalid", "Image could not be validated or hashed."))

            if candidate is not None:
                normalized = str(candidate.canonical_path).casefold()
                if normalized in seen_paths:
                    issues.append(
                        self._issue(
                            wallpaper,
                            "duplicate_record_path",
                            "This library record points to a path already scanned; counted once.",
                        )
                    )
                else:
                    seen_paths[normalized] = wallpaper.id
                    candidates.append(candidate)
            scanned += 1
            callback(scanned, len(self._wallpapers), wallpaper.filename or "Image")

        try:
            exact_groups, collision_candidates, exact_issues = self._build_exact_groups(
                candidates, cancel
            )
            issues.extend(exact_issues)
            if cancel.is_set():
                return self._report(
                    candidates, (), issues, scanned, started_at, completed=False, cancelled=True
                )
            near_groups = self._build_near_groups(collision_candidates, cancel)
        except ScanCancelledError:
            return self._report(
                candidates, (), issues, scanned, started_at, completed=False, cancelled=True
            )

        return self._report(
            candidates,
            (*exact_groups, *near_groups),
            issues,
            scanned,
            started_at,
            completed=True,
            cancelled=False,
        )

    def _scan_one(
        self,
        wallpaper: Wallpaper,
        cancel_event: threading.Event,
    ) -> DuplicateCandidate | None:
        if wallpaper.id is None:
            raise ValueError("Library record has no ID.")
        if not wallpaper.path:
            raise FileNotFoundError
        path = Path(wallpaper.path).resolve(strict=True)
        identity = _file_identity(path)
        if path.suffix.lower() not in SUPPORTED_FORMATS:
            raise InvalidImageError("Unsupported image extension.")
        valid, _reason = validate_image_file(path)
        if not valid:
            raise InvalidImageError("Image validation failed.")
        _check_cancelled(cancel_event)

        sha256 = _hash_file(path, identity, cancel_event)
        phash = compute_phash(path)
        _check_cancelled(cancel_event)
        if len(phash) != 16:
            raise InvalidImageError("Could not calculate pHash.")
        try:
            int(phash, 16)
        except ValueError:
            raise InvalidImageError("Could not calculate pHash.") from None

        if _file_identity(path) != identity:
            raise OSError("File changed during scanning.")
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format or path.suffix.lstrip(".").upper()
        if _file_identity(path) != identity:
            raise OSError("File changed while reading image metadata.")
        return DuplicateCandidate(
            wallpaper=wallpaper,
            canonical_path=path,
            sha256=sha256,
            phash=phash,
            size_bytes=identity.size_bytes,
            width=width,
            height=height,
            image_format=image_format.upper(),
            identity=identity,
        )

    def _build_exact_groups(
        self,
        candidates: Sequence[DuplicateCandidate],
        cancel_event: threading.Event,
    ) -> tuple[list[DuplicateGroup], list[DuplicateCandidate], list[ScanIssue]]:
        by_sha: dict[str, list[DuplicateCandidate]] = defaultdict(list)
        for candidate in candidates:
            by_sha[candidate.sha256].append(candidate)

        groups: list[DuplicateGroup] = []
        usable_for_near: list[DuplicateCandidate] = []
        issues: list[ScanIssue] = []
        for sha256, same_hash in sorted(by_sha.items()):
            if len(same_hash) == 1:
                usable_for_near.extend(same_hash)
                continue

            byte_clusters: list[list[DuplicateCandidate]] = []
            for candidate in same_hash:
                _check_cancelled(cancel_event)
                placed = False
                for cluster in byte_clusters:
                    representative = cluster[0]
                    try:
                        if _same_bytes(representative, candidate, cancel_event):
                            cluster.append(candidate)
                            placed = True
                            break
                    except ScanCancelledError:
                        raise
                    except OSError:
                        issues.append(
                            self._issue(
                                candidate.wallpaper,
                                "changed",
                                "File changed or became unavailable during byte verification.",
                            )
                        )
                        placed = True
                        break
                if not placed:
                    byte_clusters.append([candidate])

            if len(byte_clusters) > 1:
                for cluster in byte_clusters:
                    for candidate in cluster:
                        issues.append(
                            self._issue(
                                candidate.wallpaper,
                                "hash_collision",
                                "Matching SHA-256 values did not verify as identical bytes.",
                            )
                        )

            for cluster in byte_clusters:
                if len(cluster) >= 2:
                    ordered = tuple(sorted(cluster, key=self._candidate_key))
                    ids = ",".join(str(item.wallpaper_id) for item in ordered)
                    groups.append(
                        DuplicateGroup(
                            group_id=f"exact:{sha256}:{hashlib.sha256(ids.encode()).hexdigest()[:12]}",
                            kind="exact",
                            members=ordered,
                        )
                    )
                    usable_for_near.append(ordered[0])
                else:
                    usable_for_near.extend(cluster)

        groups.sort(key=lambda group: group.group_id)
        usable_for_near.sort(key=self._candidate_key)
        return groups, usable_for_near, issues

    def _build_near_groups(
        self,
        candidates: Sequence[DuplicateCandidate],
        cancel_event: threading.Event,
    ) -> list[DuplicateGroup]:
        tree = _BKTree()
        edges: list[SimilarityEdge] = []
        for index, candidate in enumerate(candidates):
            _check_cancelled(cancel_event)
            value = int(candidate.phash, 16)
            for other_index, distance in tree.query(value, self._threshold):
                other = candidates[other_index]
                edges.append(
                    SimilarityEdge(
                        first_id=other.wallpaper_id,
                        second_id=candidate.wallpaper_id,
                        hamming_distance=distance,
                        similarity_percent=_similarity(distance),
                    )
                )
            tree.add(value, index)

        if not edges:
            return []

        parent = {candidate.wallpaper_id: candidate.wallpaper_id for candidate in candidates}

        def find(item_id: int) -> int:
            while parent[item_id] != item_id:
                parent[item_id] = parent[parent[item_id]]
                item_id = parent[item_id]
            return item_id

        for edge in edges:
            first = find(edge.first_id)
            second = find(edge.second_id)
            if first != second:
                parent[max(first, second)] = min(first, second)

        grouped_members: dict[int, list[DuplicateCandidate]] = defaultdict(list)
        for candidate in candidates:
            root = find(candidate.wallpaper_id)
            grouped_members[root].append(candidate)

        grouped_edges: dict[int, list[SimilarityEdge]] = defaultdict(list)
        for edge in edges:
            grouped_edges[find(edge.first_id)].append(edge)

        groups: list[DuplicateGroup] = []
        for root_id, members in grouped_members.items():
            if len(members) < 2:
                continue
            ordered = tuple(sorted(members, key=self._candidate_key))
            ordered_edges = tuple(
                sorted(
                    grouped_edges[root_id],
                    key=lambda edge: (-edge.similarity_percent, edge.first_id, edge.second_id),
                )
            )
            member_ids = ",".join(str(item.wallpaper_id) for item in ordered)
            group_digest = hashlib.sha256(member_ids.encode()).hexdigest()[:12]
            groups.append(DuplicateGroup(f"near:{group_digest}", "near", ordered, ordered_edges))
        groups.sort(key=lambda group: group.group_id)
        return groups

    @staticmethod
    def _candidate_key(candidate: DuplicateCandidate) -> tuple[str, str, int]:
        return (
            candidate.canonical_path.as_posix().casefold(),
            candidate.sha256,
            candidate.wallpaper_id,
        )

    @staticmethod
    def _issue(wallpaper: Wallpaper, code: str, message: str) -> ScanIssue:
        return ScanIssue(wallpaper.id, wallpaper.filename or Path(wallpaper.path).name or "Image", code, message)

    def _report(
        self,
        candidates: Sequence[DuplicateCandidate],
        groups: Sequence[DuplicateGroup],
        issues: Sequence[ScanIssue],
        scanned: int,
        started_at: str,
        *,
        completed: bool,
        cancelled: bool,
    ) -> DuplicateScanReport:
        return DuplicateScanReport(
            threshold=self._threshold,
            total_records=len(self._wallpapers),
            scanned_records=scanned,
            candidates=tuple(candidates),
            groups=tuple(groups),
            issues=tuple(issues),
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            completed=completed,
            cancelled=cancelled,
        )


def build_cleanup_preview(
    report: DuplicateScanReport,
    removals_by_group: Mapping[str, set[int]],
    keep_by_group: Mapping[str, int],
    cancel_event: threading.Event | None = None,
) -> CleanupPreview:
    """Validate and summarize a proposed plan without changing files or rows."""
    if not report.completed or report.cancelled:
        raise CleanupPreviewError("Run a complete duplicate scan before previewing a plan.")
    cancel = cancel_event or threading.Event()

    groups_by_id = {group.group_id: group for group in report.groups}
    selected_entries: list[CleanupPreviewEntry] = []
    removed_ids: set[int] = set()
    kept_ids: set[int] = set()

    for group_id, remove_ids in removals_by_group.items():
        if not remove_ids:
            continue
        group = groups_by_id.get(group_id)
        if group is None:
            raise CleanupPreviewError("A selected group is no longer in the scan results.")
        keep_id = keep_by_group.get(group_id)
        members_by_id = {candidate.wallpaper_id: candidate for candidate in group.members}
        if keep_id is None or keep_id not in members_by_id:
            raise CleanupPreviewError("Choose one file to retain in every selected group.")
        if keep_id in remove_ids:
            raise CleanupPreviewError("A retained file cannot also be selected for removal.")
        if not remove_ids.issubset(members_by_id):
            raise CleanupPreviewError("A selected file does not belong to its duplicate group.")
        if len(remove_ids) >= len(group.members):
            raise CleanupPreviewError("Keep at least one file in every selected group.")
        if group.kind == "exact" and keep_id not in members_by_id:
            raise CleanupPreviewError("Exact groups require a retained member.")

        selected_entries.append(
            CleanupPreviewEntry(
                group_id=group_id,
                retained=members_by_id[keep_id],
                selected_for_removal=tuple(
                    members_by_id[item_id]
                    for item_id in sorted(remove_ids)
                ),
            )
        )
        removed_ids.update(remove_ids)
        kept_ids.add(keep_id)

    if not selected_entries:
        raise CleanupPreviewError("Select one or more files for the preview plan.")
    if removed_ids & kept_ids:
        raise CleanupPreviewError(
            "A file is selected for removal in one group and retention in another. Resolve the overlap first."
        )
    removal_occurrences = sum(len(entry.selected_for_removal) for entry in selected_entries)
    if removal_occurrences != len(removed_ids):
        raise CleanupPreviewError("A file is selected in more than one group. Resolve the overlap first.")

    to_revalidate = {
        candidate.wallpaper_id: candidate
        for entry in selected_entries
        for candidate in (entry.retained, *entry.selected_for_removal)
    }
    for candidate in to_revalidate.values():
        _check_cancelled(cancel)
        try:
            before = _file_identity(candidate.canonical_path)
            if before != candidate.identity:
                raise CleanupPreviewError(
                    f"{candidate.display_name} changed after the scan; rescan before previewing."
                )
            current_sha = _sha256_readonly(candidate.canonical_path, cancel)
            valid, _reason = validate_image_file(candidate.canonical_path)
            after = _file_identity(candidate.canonical_path)
        except CleanupPreviewError:
            raise
        except (OSError, ValueError):
            raise CleanupPreviewError(
                f"{candidate.display_name} is missing or unreadable; rescan before previewing."
            ) from None
        if before != after or current_sha != candidate.sha256 or not valid:
            raise CleanupPreviewError(
                f"{candidate.display_name} no longer matches the scan; rescan before previewing."
            )

    for entry in selected_entries:
        group = groups_by_id[entry.group_id]
        if not any(item.wallpaper_id == entry.retained.wallpaper_id for item in group.members):
            raise CleanupPreviewError("Each plan group must retain a valid scanned member.")
        if group.kind == "near":
            direct_pairs = {
                frozenset((edge.first_id, edge.second_id))
                for edge in group.edges
                if edge.hamming_distance <= report.threshold
            }
            for candidate in entry.selected_for_removal:
                if frozenset((entry.retained.wallpaper_id, candidate.wallpaper_id)) not in direct_pairs:
                    raise CleanupPreviewError(
                        f"{candidate.display_name} is not a direct near match to the retained file; choose a different retained item."
                    )
        elif group.kind == "exact":
            for candidate in entry.selected_for_removal:
                try:
                    _check_cancelled(cancel)
                    identical = _byte_paths_equal(
                        entry.retained.canonical_path,
                        candidate.canonical_path,
                        cancel,
                    )
                except ScanCancelledError:
                    raise CleanupPreviewError("Preview was cancelled.") from None
                except OSError:
                    identical = False
                if not identical:
                    raise CleanupPreviewError(
                        f"{candidate.display_name} is not byte-identical to its retained copy; rescan."
                    )

    return CleanupPreview(
        entries=tuple(selected_entries),
        files_selected=len(removed_ids),
        estimated_bytes=sum(
            candidate.size_bytes
            for entry in selected_entries
            for candidate in entry.selected_for_removal
        ),
    )


def _sha256_readonly(path: Path, cancel_event: threading.Event) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while True:
            _check_cancelled(cancel_event)
            chunk = file_handle.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _byte_paths_equal(
    first_path: Path,
    second_path: Path,
    cancel_event: threading.Event,
) -> bool:
    with first_path.open("rb") as first_file, second_path.open("rb") as second_file:
        while True:
            _check_cancelled(cancel_event)
            first_chunk = first_file.read(_HASH_CHUNK_SIZE)
            second_chunk = second_file.read(_HASH_CHUNK_SIZE)
            if first_chunk != second_chunk:
                return False
            if not first_chunk:
                return True
