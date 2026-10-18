"""
Sandy Wallpaper Studio - Import Service
==========================================
Phase 4: Smart Library — Folder Import & Indexing

Orchestrates the import of wallpaper images from local folders:
- Recursive or flat folder scanning
- Per-file validation, metadata extraction, hashing
- Exact and near-duplicate detection
- Thumbnail generation
- Database persistence with transaction safety
- Structured import reporting

Never deletes, moves, or modifies original user files.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from app.constants import (
    DEFAULT_LIBRARY_DIR_NAME,
    SUPPORTED_FORMATS,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
)
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.duplicate_service import DuplicateService
from app.services.metadata_service import ImageValidationError, MetadataService
from app.utils.hashing import compute_phash
from app.utils.image_utils import create_thumbnail, validate_image_file

logger = logging.getLogger(__name__)


# ============================================================
# Import Result Types
# ============================================================
class FileStatus(Enum):
    """Status of a single file during import."""
    IMPORTED = "imported"
    SKIPPED_UNSUPPORTED = "skipped_unsupported"
    SKIPPED_INVALID = "skipped_invalid"
    SKIPPED_UNREADABLE = "skipped_unreadable"
    SKIPPED_EXACT_DUPLICATE = "skipped_exact_duplicate"
    SKIPPED_ALREADY_INDEXED = "skipped_already_indexed"
    NEAR_DUPLICATE_IMPORTED = "near_duplicate_imported"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FileResult:
    """Result of processing a single file during import."""
    path: Path
    status: FileStatus
    message: str = ""
    wallpaper_id: Optional[int] = None
    near_duplicate_ids: list[int] = field(default_factory=list)


@dataclass
class ImportReport:
    """Structured summary of an import operation."""
    source_folder: str = ""
    recursive: bool = False
    started_at: str = ""
    completed_at: str = ""
    total_discovered: int = 0
    total_imported: int = 0
    total_skipped: int = 0
    total_invalid: int = 0
    total_exact_duplicates: int = 0
    total_near_duplicates: int = 0
    total_already_indexed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0
    file_results: list[FileResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def was_cancelled(self) -> bool:
        return self.total_cancelled > 0

    def summary_dict(self) -> dict:
        """Return a concise summary without per-file details."""
        return {
            "source_folder": self.source_folder,
            "recursive": self.recursive,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "discovered": self.total_discovered,
            "imported": self.total_imported,
            "skipped": self.total_skipped,
            "invalid": self.total_invalid,
            "exact_duplicates": self.total_exact_duplicates,
            "near_duplicates": self.total_near_duplicates,
            "already_indexed": self.total_already_indexed,
            "failed": self.total_failed,
            "cancelled": self.total_cancelled,
            "errors": self.errors,
        }


# Progress callback: (current_file_index, total_files, current_filename)
ImportProgressCallback = Callable[[int, int, str], None]


class ImportService:
    """Service for importing wallpaper images from local folders.

    Orchestrates the full import pipeline:
    1. Scan folder for image files
    2. For each file: validate → extract metadata → hash → check duplicates
       → generate thumbnail → persist to database
    3. Report results

    Thread-safety: Each import operation should use its own ImportService instance
    or be serialized. The database operations use per-file commits.
    """

    def __init__(
        self,
        db: Database,
        cache_dir: Optional[Path] = None,
        phash_threshold: int = 10,
    ) -> None:
        if cache_dir is None:
            cache_dir = Path.home() / "Pictures" / DEFAULT_LIBRARY_DIR_NAME / "Cache"
        self._db = db
        self._repo = WallpaperRepository(db)
        self._metadata_svc = MetadataService()
        self._duplicate_svc = DuplicateService(db, threshold=phash_threshold)
        self._cache_dir = cache_dir
        self._thumbnail_dir = cache_dir / "thumbnails"
        self._thumbnail_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def import_folder(
        self,
        folder_path: Path,
        recursive: bool = False,
        category: str = "",
        progress_callback: Optional[ImportProgressCallback] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> ImportReport:
        """Import images from a folder into the wallpaper library.

        Args:
            folder_path: Path to the folder to import from.
            recursive: If True, scan subdirectories recursively.
            category: Optional category to assign to imported wallpapers.
            progress_callback: Called with (current_index, total, filename).
            cancelled: Callable returning True to cancel the import.

        Returns:
            ImportReport with detailed results for each file.
        """
        report = ImportReport(
            source_folder=str(folder_path),
            recursive=recursive,
            started_at=datetime.now(UTC).isoformat(),
        )

        # Validate folder
        folder = Path(folder_path)
        if not folder.exists():
            report.errors.append(f"Folder not found: {folder}")
            report.completed_at = datetime.now(UTC).isoformat()
            return report

        if not folder.is_dir():
            report.errors.append(f"Not a directory: {folder}")
            report.completed_at = datetime.now(UTC).isoformat()
            return report

        # Discover image files
        logger.info("Scanning folder: %s (recursive=%s)", folder, recursive)
        image_files = self._scan_folder(folder, recursive)
        report.total_discovered = len(image_files)
        logger.info("Discovered %d potential image files.", len(image_files))

        if not image_files:
            report.completed_at = datetime.now(UTC).isoformat()
            return report

        # Process each file
        for idx, file_path in enumerate(image_files):
            # Check cancellation
            if cancelled and cancelled():
                remaining = len(image_files) - idx
                report.total_cancelled = remaining
                for remaining_path in image_files[idx:]:
                    report.file_results.append(FileResult(
                        path=remaining_path,
                        status=FileStatus.CANCELLED,
                        message="Import cancelled by user.",
                    ))
                logger.info("Import cancelled at file %d/%d.", idx, len(image_files))
                break

            # Progress callback
            if progress_callback:
                progress_callback(idx + 1, len(image_files), file_path.name)

            # Process the file
            result = self._process_file(file_path, category)
            report.file_results.append(result)

            # Update counters
            match result.status:
                case FileStatus.IMPORTED:
                    report.total_imported += 1
                case FileStatus.NEAR_DUPLICATE_IMPORTED:
                    report.total_imported += 1
                    report.total_near_duplicates += 1
                case FileStatus.SKIPPED_UNSUPPORTED:
                    report.total_skipped += 1
                case FileStatus.SKIPPED_INVALID:
                    report.total_invalid += 1
                case FileStatus.SKIPPED_UNREADABLE:
                    report.total_invalid += 1
                case FileStatus.SKIPPED_EXACT_DUPLICATE:
                    report.total_exact_duplicates += 1
                case FileStatus.SKIPPED_ALREADY_INDEXED:
                    report.total_already_indexed += 1
                case FileStatus.FAILED:
                    report.total_failed += 1
                    report.errors.append(f"{file_path.name}: {result.message}")
                case FileStatus.CANCELLED:
                    report.total_cancelled += 1

        report.completed_at = datetime.now(UTC).isoformat()
        logger.info(
            "Import complete: %d imported, %d skipped, %d duplicates, %d failed "
            "out of %d discovered.",
            report.total_imported, report.total_skipped,
            report.total_exact_duplicates, report.total_failed,
            report.total_discovered,
        )
        return report

    # ----------------------------------------------------------
    # Folder Scanning
    # ----------------------------------------------------------
    def _scan_folder(self, folder: Path, recursive: bool) -> list[Path]:
        """Scan a folder for image files, sorted by name.

        Uses os.scandir for efficient directory traversal without
        loading all file metadata into memory.

        Args:
            folder: Directory to scan.
            recursive: If True, scan subdirectories.

        Returns:
            Sorted list of image file paths.
        """
        image_files: list[Path] = []

        try:
            if recursive:
                for root, _dirs, files in os.walk(folder):
                    for name in files:
                        file_path = Path(root) / name
                        if file_path.suffix.lower() in SUPPORTED_FORMATS:
                            image_files.append(file_path)
            else:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if entry.is_file():
                            path = Path(entry.path)
                            if path.suffix.lower() in SUPPORTED_FORMATS:
                                image_files.append(path)
        except PermissionError as exc:
            logger.error("Permission denied scanning folder: %s", exc)
        except OSError as exc:
            logger.error("Error scanning folder: %s", exc)

        image_files.sort(key=lambda p: p.name.lower())
        return image_files

    # ----------------------------------------------------------
    # Per-File Processing
    # ----------------------------------------------------------
    def _process_file(self, file_path: Path, category: str) -> FileResult:
        """Process a single image file through the full import pipeline.

        Pipeline:
        1. Check file accessibility
        2. Check if already indexed by path
        3. Validate image format and integrity
        4. Extract metadata (dimensions, format, file size)
        5. Compute SHA-256 hash
        6. Check for exact duplicates
        7. Compute perceptual hash
        8. Check for near duplicates
        9. Generate thumbnail
        10. Create database record

        Args:
            file_path: Path to the image file.
            category: Category to assign.

        Returns:
            FileResult with the processing outcome.
        """
        # 1. Check file accessibility
        if not file_path.exists():
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_UNREADABLE,
                message="File not found.",
            )

        if not file_path.is_file():
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_UNSUPPORTED,
                message="Not a regular file.",
            )

        # Check supported format
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_UNSUPPORTED,
                message=f"Unsupported format: {suffix}",
            )

        # 2. Check if already indexed by path
        normalized_path = str(file_path.resolve())
        existing_by_path = self._repo.get_by_path(normalized_path)
        if existing_by_path is not None:
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_ALREADY_INDEXED,
                message=f"Already indexed (id={existing_by_path.id}).",
                wallpaper_id=existing_by_path.id,
            )

        # 3. Validate image integrity
        is_valid, error_msg = validate_image_file(file_path)
        if not is_valid:
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_INVALID,
                message=error_msg,
            )

        # 4. Extract metadata
        try:
            metadata = self._metadata_svc.extract(file_path)
        except ImageValidationError as exc:
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_INVALID,
                message=str(exc),
            )
        except OSError as exc:
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_UNREADABLE,
                message=f"Cannot read file: {exc}",
            )

        # 5. SHA-256 (already computed by metadata service, but compute
        #    separately for clarity and to use the canonical hashing utility)
        sha256 = metadata.sha256

        # 6. Check for exact duplicates by SHA-256
        exact_dup = self._duplicate_svc.check_exact_duplicate(sha256)
        if exact_dup is not None:
            return FileResult(
                path=file_path,
                status=FileStatus.SKIPPED_EXACT_DUPLICATE,
                message=(
                    f"Exact duplicate of '{exact_dup.filename}' "
                    f"(id={exact_dup.id})."
                ),
                wallpaper_id=exact_dup.id,
            )

        # 7. Compute perceptual hash
        phash = compute_phash(file_path)

        # 8. Check for near duplicates (report but DO NOT block import)
        near_dup_ids: list[int] = []
        if phash:
            near_matches = self._duplicate_svc.find_near_duplicates(phash)
            near_dup_ids = [
                m.original.id for m in near_matches
                if m.original.id is not None
            ]

        # 9. Generate thumbnail
        thumb_filename = f"{sha256[:16]}.jpg"
        thumb_path = self._thumbnail_dir / thumb_filename
        if not thumb_path.exists():
            create_thumbnail(
                file_path, thumb_path,
                size=THUMBNAIL_SIZE, quality=THUMBNAIL_QUALITY,
            )

        # 10. Create database record
        try:
            wallpaper = Wallpaper(
                filename=file_path.name,
                path=normalized_path,
                title=file_path.stem.replace("_", " ").replace("-", " "),
                description="",
                category=category,
                tags="",
                width=metadata.width,
                height=metadata.height,
                aspect_ratio=metadata.aspect_ratio,
                resolution_class=metadata.resolution_class,
                file_size=metadata.file_size,
                sha256=sha256,
                phash=phash,
                source="local_import",
                source_url="",
                author="",
                license="",
                license_url="",
                download_date=datetime.now(UTC).isoformat(),
                favorite=False,
                last_used=None,
                usage_count=0,
            )
            new_id = self._repo.add(wallpaper)

            status = FileStatus.IMPORTED
            message = f"Imported successfully (id={new_id})."
            if near_dup_ids:
                status = FileStatus.NEAR_DUPLICATE_IMPORTED
                message = (
                    f"Imported (id={new_id}) with {len(near_dup_ids)} "
                    f"potential near-duplicate(s): {near_dup_ids}"
                )

            logger.debug(
                "Imported: %s → id=%d (%s, %s)",
                file_path.name, new_id,
                metadata.resolution_class, metadata.aspect_ratio,
            )

            return FileResult(
                path=file_path,
                status=status,
                message=message,
                wallpaper_id=new_id,
                near_duplicate_ids=near_dup_ids,
            )

        except Exception as exc:
            # Roll back to prevent incomplete records
            try:
                self._db.rollback()
            except Exception:
                pass
            logger.error("Failed to save wallpaper record for %s: %s", file_path, exc)
            return FileResult(
                path=file_path,
                status=FileStatus.FAILED,
                message=f"Database error: {exc}",
            )
