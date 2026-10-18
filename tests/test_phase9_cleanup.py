"""Safe Phase 9 cleanup workflow tests using disposable image fixtures."""

from __future__ import annotations

import os
import shutil
import stat
import threading
import time
import uuid
from pathlib import Path

import pytest
from PIL import Image

from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services.duplicate_cleanup_service import (
    CleanupSafetyError,
    execute_cleanup,
)
from app.services.duplicate_scan_service import (
    CleanupPreviewError,
    DuplicateCandidate,
    DuplicateScanService,
    FileIdentity,
    build_cleanup_preview,
)


def _make_image(path: Path, color: tuple[int, int, int] = (30, 90, 150)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (96, 54), color).save(path, format="JPEG", quality=90)
    return path


def _wallpaper(path: Path, wallpaper_id: int, favorite: bool = False) -> Wallpaper:
    return Wallpaper(
        id=wallpaper_id,
        filename=path.name,
        path=str(path),
        title=path.stem,
        width=96,
        height=54,
        file_size=path.stat().st_size,
        favorite=favorite,
        sha256="stale-indexed-sha",
        phash="stale-indexed-phash",
    )


def _synthetic_candidate(wallpaper_id: int, phash_value: int) -> DuplicateCandidate:
    path = Path(f"C:/synthetic-library/{wallpaper_id:04d}.jpg")
    wallpaper = Wallpaper(
        id=wallpaper_id,
        filename=path.name,
        path=str(path),
        file_size=1,
    )
    identity = FileIdentity(str(path), 1, wallpaper_id, 1, 1, 1)
    return DuplicateCandidate(
        wallpaper=wallpaper,
        canonical_path=path,
        sha256=f"{wallpaper_id:064x}",
        phash=f"{phash_value:016x}",
        size_bytes=1,
        width=1,
        height=1,
        image_format="JPEG",
        identity=identity,
    )


def _exact_group(tmp_path: Path, count: int = 2):
    first = _make_image(tmp_path / "library" / "a-keep.jpg")
    paths = [first]
    for index in range(2, count + 1):
        duplicate = tmp_path / "library" / f"b-copy-{index}.jpg"
        shutil.copyfile(first, duplicate)
        paths.append(duplicate)
    records = [_wallpaper(path, index) for index, path in enumerate(paths, start=1)]
    report = DuplicateScanService(records).scan()
    group = report.exact_groups[0]
    keep_id = group.members[0].wallpaper_id
    remove_ids = {member.wallpaper_id for member in group.members[1:]}
    preview = build_cleanup_preview(
        report,
        {group.group_id: remove_ids},
        {group.group_id: keep_id},
        allowed_root=tmp_path / "library",
    )
    return report, group, preview, paths


class TestCleanupSafety:
    def test_confirmed_cleanup_recycles_only_selected_target_and_preserves_keep(
        self, tmp_path: Path
    ) -> None:
        report, _group, preview, paths = _exact_group(tmp_path)
        before_keep = paths[0].read_bytes()
        calls: list[Path] = []

        def recycle(path: Path) -> None:
            calls.append(path)
            path.unlink()

        result = execute_cleanup(
            report,
            preview,
            tmp_path / "library",
            recycler=recycle,
            lock_check=lambda _path: None,
        )

        assert [item.status for item in result.results] == ["recycled"]
        assert result.recycled_count == 1
        assert calls == [paths[1]]
        assert not paths[1].exists()
        assert paths[0].read_bytes() == before_keep

    def test_cleanup_rejects_target_outside_configured_library(self, tmp_path: Path) -> None:
        report, group, _preview, paths = _exact_group(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        paths[1].replace(outside / paths[1].name)
        records = [_wallpaper(paths[0], 1), _wallpaper(outside / paths[1].name, 2)]
        report = DuplicateScanService(records).scan()
        group = report.exact_groups[0]

        with pytest.raises(CleanupPreviewError, match="outside the configured library"):
            build_cleanup_preview(
                report,
                {group.group_id: {group.members[1].wallpaper_id}},
                {group.group_id: group.members[0].wallpaper_id},
                allowed_root=tmp_path / "library",
            )

    def test_cleanup_rejects_hard_link_targets(self, tmp_path: Path) -> None:
        report, group, _preview, paths = _exact_group(tmp_path)
        alias = paths[1].with_name("alias.jpg")
        try:
            os.link(paths[1], alias)
        except OSError as exc:
            pytest.skip(f"The temporary filesystem does not support hard links: {type(exc).__name__}")

        with pytest.raises(CleanupPreviewError, match="multiple hard links"):
            build_cleanup_preview(
                report,
                {group.group_id: {group.members[1].wallpaper_id}},
                {group.group_id: group.members[0].wallpaper_id},
                allowed_root=tmp_path / "library",
            )

    def test_cleanup_rejects_symbolic_link_targets(self, tmp_path: Path) -> None:
        first = _make_image(tmp_path / "library" / "keep.jpg")
        source = _make_image(tmp_path / "library" / "source.jpg")
        link = tmp_path / "library" / "linked.jpg"
        shutil.copyfile(first, source)
        try:
            link.symlink_to(source)
        except OSError as exc:
            pytest.skip(f"The Windows profile does not permit symbolic links: {type(exc).__name__}")
        report = DuplicateScanService([_wallpaper(first, 1), _wallpaper(link, 2)]).scan()
        group = report.exact_groups[0]
        target = next(member for member in group.members if member.wallpaper.filename == link.name)

        with pytest.raises(CleanupPreviewError, match="symbolic link or reparse point"):
            build_cleanup_preview(
                report,
                {group.group_id: {target.wallpaper_id}},
                {group.group_id: next(member.wallpaper_id for member in group.members if member is not target)},
                allowed_root=tmp_path / "library",
            )

    def test_cleanup_rejects_link_target_when_symlink_creation_is_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        report, group, _preview, paths = _exact_group(tmp_path)
        target = next(
            member for member in group.members if member.wallpaper_id == 2
        )
        real_lstat = os.lstat

        def lstat_with_link_target(path):
            if Path(path) == target.canonical_path:
                values = list(real_lstat(path))
                values[0] = stat.S_IFLNK | stat.S_IRWXU
                return os.stat_result(values)
            return real_lstat(path)

        monkeypatch.setattr(os, "lstat", lstat_with_link_target)
        with pytest.raises(CleanupPreviewError, match="symbolic link or reparse point"):
            build_cleanup_preview(
                report,
                {group.group_id: {target.wallpaper_id}},
                {group.group_id: group.members[0].wallpaper_id},
                allowed_root=tmp_path / "library",
            )

    def test_lock_or_in_use_check_failure_prevents_recycle(self, tmp_path: Path) -> None:
        report, _group, preview, paths = _exact_group(tmp_path)
        calls: list[Path] = []

        def locked(_path: Path) -> None:
            raise CleanupSafetyError("The file is in use.")

        result = execute_cleanup(
            report,
            preview,
            tmp_path / "library",
            recycler=calls.append,
            lock_check=locked,
        )

        assert result.failed_count == 1
        assert result.results[0].status == "failed"
        assert "in use" in result.results[0].message
        assert not calls
        assert all(path.exists() for path in paths)

    def test_changed_target_is_revalidated_after_confirmation(self, tmp_path: Path) -> None:
        report, _group, preview, paths = _exact_group(tmp_path)
        _make_image(paths[1], (230, 25, 70))
        calls: list[Path] = []

        result = execute_cleanup(
            report,
            preview,
            tmp_path / "library",
            recycler=calls.append,
            lock_check=lambda _path: None,
        )

        assert result.failed_count == 1
        assert result.results[0].status == "failed"
        assert not calls
        assert paths[1].exists()

    def test_partial_failure_stops_later_targets_and_reports_each_file(
        self, tmp_path: Path
    ) -> None:
        report, _group, preview, paths = _exact_group(tmp_path, count=4)
        calls: list[Path] = []

        def recycle(path: Path) -> None:
            calls.append(path)
            if path == paths[2]:
                raise OSError("simulated Recycle Bin failure")
            path.unlink()

        result = execute_cleanup(
            report,
            preview,
            tmp_path / "library",
            recycler=recycle,
            lock_check=lambda _path: None,
        )

        assert [item.status for item in result.results] == ["recycled", "failed", "skipped"]
        assert calls == [paths[1], paths[2]]
        assert not paths[1].exists()
        assert paths[2].exists()
        assert paths[3].exists()

    def test_cancellation_after_one_file_keeps_per_file_outcomes(self, tmp_path: Path) -> None:
        report, _group, preview, paths = _exact_group(tmp_path, count=4)
        cancel = threading.Event()

        def recycle(path: Path) -> None:
            path.unlink()
            cancel.set()

        result = execute_cleanup(
            report,
            preview,
            tmp_path / "library",
            cancel_event=cancel,
            recycler=recycle,
            lock_check=lambda _path: None,
        )

        assert result.cancelled
        assert [item.status for item in result.results] == [
            "recycled",
            "cancelled",
            "cancelled",
        ]
        assert not paths[1].exists()
        assert paths[2].exists() and paths[3].exists()

    def test_database_favorites_history_views_and_foreign_keys_are_preserved(
        self, tmp_path: Path
    ) -> None:
        library = tmp_path / "library"
        first = _make_image(library / "keep.jpg")
        duplicate = library / "copy.jpg"
        shutil.copyfile(first, duplicate)
        database = Database(tmp_path / "isolated-library.db")
        database.connect()
        repository = WallpaperRepository(database)
        keep_id = repository.add(_wallpaper(first, 1, favorite=True))
        remove_id = repository.add(_wallpaper(duplicate, 2, favorite=True))
        database.execute(
            "INSERT INTO wallpaper_history (wallpaper_id, set_at, monitor, source, success, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (remove_id, "2026-10-19T00:00:00+00:00", "primary", "rotation", 1, ""),
        )
        database.execute(
            "INSERT INTO wallpaper_views (wallpaper_id, viewed_at) VALUES (?, ?)",
            (remove_id, "2026-10-19T00:01:00+00:00"),
        )
        database.commit()
        rows_before = [
            tuple(row)
            for row in database.execute("SELECT id, path, favorite FROM wallpapers ORDER BY id").fetchall()
        ]
        history_before = [
            tuple(row)
            for row in database.execute("SELECT * FROM wallpaper_history ORDER BY id").fetchall()
        ]
        views_before = [
            tuple(row)
            for row in database.execute("SELECT * FROM wallpaper_views ORDER BY id").fetchall()
        ]
        report = DuplicateScanService(
            [repository.get_by_id(keep_id), repository.get_by_id(remove_id)]
        ).scan()
        group = report.exact_groups[0]
        preview = build_cleanup_preview(
            report,
            {group.group_id: {remove_id}},
            {group.group_id: keep_id},
            allowed_root=library,
        )

        try:
            result = execute_cleanup(
                report,
                preview,
                library,
                recycler=lambda path: path.unlink(),
                lock_check=lambda _path: None,
            )
            assert result.recycled_count == 1
            rows_after = [
                tuple(row)
                for row in database.execute("SELECT id, path, favorite FROM wallpapers ORDER BY id").fetchall()
            ]
            history_after = [
                tuple(row)
                for row in database.execute("SELECT * FROM wallpaper_history ORDER BY id").fetchall()
            ]
            views_after = [
                tuple(row)
                for row in database.execute("SELECT * FROM wallpaper_views ORDER BY id").fetchall()
            ]
            assert rows_after == rows_before
            assert history_after == history_before
            assert views_after == views_before
            assert database.execute("PRAGMA foreign_key_check").fetchall() == []
            assert first.exists() and not duplicate.exists()
        finally:
            database.close()


class TestBoundedNearSearch:
    def test_maximum_threshold_uses_a_linear_star_of_direct_edges(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidates = {
            item_id: _synthetic_candidate(item_id, item_id)
            for item_id in range(1, 301)
        }
        wallpapers = [item.wallpaper for item in candidates.values()]
        service = DuplicateScanService(wallpapers, threshold=64)
        monkeypatch.setattr(
            service,
            "_scan_one",
            lambda wallpaper, _cancel: candidates[wallpaper.id],
        )

        report = service.scan()

        assert report.completed and report.near_complete
        assert report.exact_groups == ()
        assert len(report.near_groups) == 1
        assert len(report.near_groups[0].members) == 300
        assert len(report.near_groups[0].edges) == 299

    def test_dense_near_search_stops_at_edge_budget_with_truthful_partial_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidates = {
            item_id: _synthetic_candidate(item_id, item_id)
            for item_id in range(1, 321)
        }
        wallpapers = [item.wallpaper for item in candidates.values()]
        service = DuplicateScanService(wallpapers, threshold=9)
        monkeypatch.setattr(
            service,
            "_scan_one",
            lambda wallpaper, _cancel: candidates[wallpaper.id],
        )

        report = service.scan()

        assert report.completed
        assert not report.near_complete
        assert report.near_groups == ()
        assert len(report.candidates) == 320
        assert any(issue.code == "near_search_limit" for issue in report.issues)


@pytest.mark.skipif(
    os.environ.get("SWS_RUN_WINDOWS_RECYCLE_INTEGRATION") != "1",
    reason="Set SWS_RUN_WINDOWS_RECYCLE_INTEGRATION=1 to run the isolated Windows Recycle Bin round-trip.",
)
def test_windows_recycle_bin_round_trip(tmp_path: Path) -> None:
    """Exercise and restore one synthetic file through the real Windows Recycle Bin."""
    if os.name != "nt":
        pytest.skip("Windows Recycle Bin integration requires Windows.")
    try:
        import win32com.client
    except ImportError:
        pytest.skip("pywin32 is unavailable for verifying restoration from the Recycle Bin.")

    token = uuid.uuid4().hex
    library = tmp_path / "library"
    keep = _make_image(library / f"sws-phase9-keep-{token}.jpg")
    recycled = library / f"sws-phase9-target-{token}.jpg"
    shutil.copyfile(keep, recycled)
    report = DuplicateScanService([_wallpaper(keep, 1), _wallpaper(recycled, 2)]).scan()
    group = report.exact_groups[0]
    preview = build_cleanup_preview(
        report,
        {group.group_id: {group.members[1].wallpaper_id}},
        {group.group_id: group.members[0].wallpaper_id},
        allowed_root=library,
    )
    expected = recycled.read_bytes()
    operation = None
    item = None
    shell = win32com.client.Dispatch("Shell.Application")
    recycle_bin = shell.Namespace(10)
    assert recycle_bin is not None

    def find_recycle_item():
        expected_path = os.path.normcase(os.path.abspath(recycled))
        for candidate in recycle_bin.Items():
            if str(candidate.Name).casefold() != recycled.name.casefold():
                continue
            source_item = Path(str(candidate.Path))
            metadata = source_item.with_name("$I" + source_item.name[2:])
            try:
                raw = metadata.read_bytes()
            except OSError:
                raw = b""
            if expected_path.encode("utf-16-le").lower() in raw.lower():
                return candidate
            try:
                original_location = candidate.ExtendedProperty("System.Recycle.OriginalLocation")
            except Exception:
                original_location = None
            if original_location and os.path.normcase(
                os.path.abspath(str(original_location))
            ) == os.path.normcase(os.path.abspath(recycled.parent)):
                return candidate
        return None

    def restore_recycle_item(candidate) -> None:
        for verb in candidate.Verbs():
            name = str(verb.Name).replace("&", "").strip().casefold()
            if name in {"restore", "restore this item"}:
                recycled.parent.mkdir(parents=True, exist_ok=True)
                verb.DoIt()
                for _ in range(100):
                    if recycled.exists():
                        return
                    time.sleep(0.02)
                break
        raise AssertionError("Windows did not restore the disposable Recycle Bin item.")

    try:
        operation = execute_cleanup(report, preview, library)
        assert operation.recycled_count == 1
        assert not recycled.exists()
        item = find_recycle_item()
        assert item is not None, "The unique synthetic target was not listed in the Recycle Bin."
        restore_recycle_item(item)
        assert recycled.read_bytes() == expected
        assert keep.exists()
    finally:
        if not recycled.exists():
            item = item or find_recycle_item()
            if item is not None:
                restore_recycle_item(item)
