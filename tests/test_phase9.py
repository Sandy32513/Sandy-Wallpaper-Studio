"""Phase 9 tests for read-only duplicate scanning and review previews."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtTest import QTest

from app.config import Config
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services import duplicate_scan_service as scan_module
from app.services.duplicate_scan_service import (
    CleanupPreviewError,
    DuplicateScanService,
    build_cleanup_preview,
    validate_threshold,
)
from app.ui import duplicate_manager_view as duplicate_ui_module
from app.ui.duplicate_manager_view import DuplicateManagerView
from app.ui.main_window import MainWindow


def _make_image(path: Path, color: tuple[int, int, int] = (50, 100, 150)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 90), color=color).save(path, format="JPEG", quality=90)
    return path


def _wallpaper(path: Path, item_id: int) -> Wallpaper:
    return Wallpaper(
        id=item_id,
        filename=path.name,
        path=str(path),
        title=path.stem,
        width=160,
        height=90,
    )


def _group_for(report, kind: str):
    return next(group for group in report.groups if group.kind == kind)


class TestDuplicateScanService:
    def test_exact_groups_verify_bytes_and_count_conservative_savings(self, tmp_path: Path) -> None:
        first_path = _make_image(tmp_path / "first.jpg")
        copy_path = tmp_path / "copy.jpg"
        shutil.copyfile(first_path, copy_path)
        other_path = _make_image(tmp_path / "other.jpg", (80, 120, 200))
        stale_hash_record = _wallpaper(first_path, 1)
        stale_hash_record.sha256 = "0" * 64
        stale_hash_record.phash = "not-a-valid-hash"

        report = DuplicateScanService(
            [stale_hash_record, _wallpaper(copy_path, 2), _wallpaper(other_path, 3)],
            threshold=0,
        ).scan()

        assert report.completed and not report.cancelled
        assert len(report.exact_groups) == 1
        exact = report.exact_groups[0]
        assert {item.wallpaper_id for item in exact.members} == {1, 2}
        assert exact.exact_redundant_bytes == first_path.stat().st_size
        assert report.exact_redundant_bytes_estimate == first_path.stat().st_size
        assert all(issue.code != "hash_collision" for issue in report.issues)

    def test_reencoded_resized_visuals_are_near_not_exact_and_results_are_stable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        jpeg = tmp_path / "visual.jpg"
        png = tmp_path / "visual-resized.png"
        distant = tmp_path / "unrelated.webp"
        Image.new("RGB", (160, 90), (30, 80, 130)).save(jpeg, format="JPEG", quality=55)
        Image.new("RGB", (320, 180), (30, 80, 130)).save(png, format="PNG")
        Image.new("RGB", (160, 90), (230, 15, 35)).save(distant, format="WEBP")
        hashes = {jpeg: "0000000000000000", png: "0000000000000000", distant: "ffffffffffffffff"}
        monkeypatch.setattr(scan_module, "compute_phash", lambda path: hashes[path])
        records = [_wallpaper(jpeg, 1), _wallpaper(png, 2), _wallpaper(distant, 3)]

        first = DuplicateScanService(records, 0).scan()
        second = DuplicateScanService(records, 0).scan()

        assert not first.exact_groups
        assert len(first.near_groups) == 1
        near = first.near_groups[0]
        assert {candidate.wallpaper_id for candidate in near.members} == {1, 2}
        assert {candidate.image_format for candidate in near.members} == {"JPEG", "PNG"}
        assert {candidate.width for candidate in near.members} == {160, 320}
        assert [group.group_id for group in first.groups] == [group.group_id for group in second.groups]
        no_match = DuplicateScanService([records[0], records[2]], 0).scan()
        assert not no_match.groups

    def test_near_match_threshold_is_inclusive_and_groups_use_direct_edges(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        paths = [
            _make_image(tmp_path / "zero.jpg", (10, 20, 30)),
            _make_image(tmp_path / "one.jpg", (40, 50, 60)),
            _make_image(tmp_path / "two.jpg", (70, 80, 90)),
        ]
        hashes = {paths[0]: "0000000000000000", paths[1]: "0000000000000001", paths[2]: "0000000000000003"}
        monkeypatch.setattr(scan_module, "compute_phash", lambda path: hashes[path])

        report = DuplicateScanService([_wallpaper(path, i + 1) for i, path in enumerate(paths)], 1).scan()

        assert len(report.near_groups) == 1
        group = report.near_groups[0]
        assert {item.wallpaper_id for item in group.members} == {1, 2, 3}
        assert sorted(edge.hamming_distance for edge in group.edges) == [1, 1]
        assert group.highest_similarity == 98.44

    def test_empty_library_and_invalid_thresholds(self) -> None:
        assert DuplicateScanService([], 10).scan().completed
        assert validate_threshold(0) == 0
        assert validate_threshold(64) == 64
        for value in (-1, 65, True, 1.5, "2"):
            with pytest.raises(ValueError):
                validate_threshold(value)  # type: ignore[arg-type]

    def test_invalid_and_missing_paths_are_reported_without_absolute_paths(self, tmp_path: Path) -> None:
        unsupported = tmp_path / "unsupported.gif"
        Image.new("RGB", (16, 16)).save(unsupported, format="GIF")
        corrupt = tmp_path / "corrupt.jpg"
        corrupt.write_bytes(b"not an image")
        missing = tmp_path / "not-here.jpg"
        report = DuplicateScanService(
            [_wallpaper(unsupported, 1), _wallpaper(corrupt, 2), _wallpaper(missing, 3)]
        ).scan()

        assert {issue.code for issue in report.issues} == {"invalid", "missing"}
        assert all(str(tmp_path) not in issue.message for issue in report.issues)
        assert all(str(tmp_path) not in issue.filename for issue in report.issues)

    def test_changed_during_hash_is_not_returned_as_candidate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _make_image(tmp_path / "change.jpg")
        original_hash_file = scan_module._hash_file

        def mutate_after_hash(file_path, identity, cancel_event):
            result = original_hash_file(file_path, identity, cancel_event)
            replacement = file_path.with_name("replacement.jpg")
            Image.new("RGB", (160, 90), color=(240, 20, 40)).save(replacement, format="JPEG", quality=90)
            replacement.replace(file_path)
            return result

        monkeypatch.setattr(scan_module, "_hash_file", mutate_after_hash)
        report = DuplicateScanService([_wallpaper(path, 1)]).scan()

        assert not report.candidates
        assert [issue.code for issue in report.issues] == ["changed"]

    def test_cancellation_discards_partial_groups(self, tmp_path: Path) -> None:
        first = _make_image(tmp_path / "first.jpg")
        second = tmp_path / "second.jpg"
        shutil.copyfile(first, second)
        cancel = threading.Event()

        def progress(done: int, _total: int, _name: str) -> None:
            if done == 1:
                cancel.set()

        report = DuplicateScanService([_wallpaper(first, 1), _wallpaper(second, 2)]).scan(cancel, progress)

        assert report.cancelled
        assert not report.completed
        assert report.scanned_records == 1
        assert not report.groups


class TestCleanupPlanPreview:
    def _exact_report(self, tmp_path: Path):
        first = _make_image(tmp_path / "keep.jpg")
        duplicate = tmp_path / "remove.jpg"
        shutil.copyfile(first, duplicate)
        report = DuplicateScanService([_wallpaper(first, 1), _wallpaper(duplicate, 2)]).scan()
        return report, first, duplicate, _group_for(report, "exact")

    def test_valid_preview_revalidates_but_changes_no_file(self, tmp_path: Path) -> None:
        report, first, duplicate, group = self._exact_report(tmp_path)
        before = {path: path.read_bytes() for path in (first, duplicate)}

        preview = build_cleanup_preview(report, {group.group_id: {2}}, {group.group_id: 1})

        assert preview.files_selected == 1
        assert preview.estimated_bytes == first.stat().st_size
        assert first.read_bytes() == before[first]
        assert duplicate.read_bytes() == before[duplicate]
        assert sorted(path.name for path in tmp_path.iterdir()) == ["keep.jpg", "remove.jpg"]

    def test_preview_requires_explicit_retained_member_and_rejects_overlap(self, tmp_path: Path) -> None:
        report, _first, _duplicate, group = self._exact_report(tmp_path)
        with pytest.raises(CleanupPreviewError, match="Choose one file"):
            build_cleanup_preview(report, {group.group_id: {2}}, {})
        with pytest.raises(CleanupPreviewError, match="cannot also"):
            build_cleanup_preview(report, {group.group_id: {1, 2}}, {group.group_id: 1})

    def test_preview_rejects_file_changed_after_scan(self, tmp_path: Path) -> None:
        report, _first, duplicate, group = self._exact_report(tmp_path)
        Image.new("RGB", (160, 90), color=(10, 240, 20)).save(duplicate, format="JPEG")

        with pytest.raises(CleanupPreviewError, match="changed after the scan"):
            build_cleanup_preview(report, {group.group_id: {2}}, {group.group_id: 1})

    def test_near_preview_requires_direct_match_to_retained_candidate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        paths = [
            _make_image(tmp_path / "zero.jpg", (10, 20, 30)),
            _make_image(tmp_path / "one.jpg", (40, 50, 60)),
            _make_image(tmp_path / "two.jpg", (70, 80, 90)),
        ]
        hashes = {paths[0]: "0000000000000000", paths[1]: "0000000000000001", paths[2]: "0000000000000003"}
        monkeypatch.setattr(scan_module, "compute_phash", lambda path: hashes[path])
        report = DuplicateScanService([_wallpaper(path, i + 1) for i, path in enumerate(paths)], 1).scan()
        group = _group_for(report, "near")

        with pytest.raises(CleanupPreviewError, match="not a direct near match"):
            build_cleanup_preview(report, {group.group_id: {3}}, {group.group_id: 1})

    def test_preview_leaves_database_rows_and_schema_unchanged(self, tmp_path: Path) -> None:
        first = _make_image(tmp_path / "db-keep.jpg")
        duplicate = tmp_path / "db-remove.jpg"
        shutil.copyfile(first, duplicate)
        database = Database(tmp_path / "preview-library.db")
        database.connect()
        repository = WallpaperRepository(database)
        repository.add(_wallpaper(first, 1))
        repository.add(_wallpaper(duplicate, 2))
        rows_before = [tuple(row) for row in database.execute("SELECT * FROM wallpapers ORDER BY id").fetchall()]
        schema_before = [tuple(row) for row in database.execute("SELECT * FROM schema_version ORDER BY version").fetchall()]
        report = DuplicateScanService(repository.get_all(limit=10, order_by="id ASC")).scan()
        group = _group_for(report, "exact")
        try:
            build_cleanup_preview(report, {group.group_id: {2}}, {group.group_id: 1})
            rows_after = [tuple(row) for row in database.execute("SELECT * FROM wallpapers ORDER BY id").fetchall()]
            schema_after = [tuple(row) for row in database.execute("SELECT * FROM schema_version ORDER BY version").fetchall()]
            assert rows_after == rows_before
            assert schema_after == schema_before
        finally:
            database.close()


class TestReadOnlyDuplicateDatabase:
    def test_read_only_database_does_not_migrate_or_write(self, tmp_path: Path) -> None:
        path = tmp_path / "library.db"
        writable = Database(path)
        writable.connect()
        repository = WallpaperRepository(writable)
        row_id = repository.add(Wallpaper(filename="one.jpg", path="C:/private/one.jpg", favorite=True))
        writable.execute(
            "INSERT INTO wallpaper_history "
            "(wallpaper_id, set_at, monitor, source, success, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row_id, "2026-01-01T00:00:00+00:00", "primary", "rotation", 0, "QA event"),
        )
        writable.execute(
            "INSERT INTO wallpaper_views (wallpaper_id, viewed_at) VALUES (?, ?)",
            (row_id, "2026-01-02T00:00:00+00:00"),
        )
        writable.commit()
        schema_before = writable.execute("SELECT version, description FROM schema_version ORDER BY version").fetchall()
        history_before = writable.execute("SELECT * FROM wallpaper_history ORDER BY id").fetchall()
        views_before = writable.execute("SELECT * FROM wallpaper_views ORDER BY id").fetchall()
        writable.close()

        readonly = Database(path, read_only=True)
        readonly.connect()
        try:
            assert readonly.execute("PRAGMA query_only").fetchone()[0] == 1
            assert WallpaperRepository(readonly).get_by_id(row_id).favorite is True
            with pytest.raises(sqlite3.OperationalError):
                readonly.execute("UPDATE wallpapers SET favorite = 0 WHERE id = ?", (row_id,))
        finally:
            readonly.close()

        check = Database(path, read_only=True)
        check.connect()
        try:
            assert check.execute("SELECT favorite FROM wallpapers WHERE id = ?", (row_id,)).fetchone()[0] == 1
            schema_after = check.execute("SELECT version, description FROM schema_version ORDER BY version").fetchall()
            history_after = check.execute("SELECT * FROM wallpaper_history ORDER BY id").fetchall()
            views_after = check.execute("SELECT * FROM wallpaper_views ORDER BY id").fetchall()
            assert [tuple(row) for row in schema_after] == [tuple(row) for row in schema_before]
            assert [tuple(row) for row in history_after] == [tuple(row) for row in history_before]
            assert [tuple(row) for row in views_after] == [tuple(row) for row in views_before]
        finally:
            check.close()

    def test_read_only_connection_does_not_create_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "absent.db"
        database = Database(missing, read_only=True)
        with pytest.raises(FileNotFoundError):
            database.connect()
        assert not missing.exists()


class TestDuplicateManagerUI:
    def test_sidebar_navigation_and_safe_action_state(self, qapp, tmp_path: Path) -> None:
        db = Database(tmp_path / "ui.db")
        db.connect()
        window = MainWindow(Config(tmp_path / "ui-config"), db)
        window.show()
        qapp.processEvents()
        try:
            QTest.mouseClick(window._sidebar._buttons["duplicates"], Qt.MouseButton.LeftButton)
            qapp.processEvents()
            view = window._views["duplicates"]
            assert isinstance(view, DuplicateManagerView)
            assert window._stack.currentWidget() is view
            assert view.scan_button.isEnabled()
            assert not view.delete_button.isEnabled()
            assert not view.preview_button.isEnabled()
        finally:
            window.close()

    def test_manager_scrolls_at_compact_size(self, qapp, tmp_path: Path) -> None:
        first = _make_image(tmp_path / "scroll-first.jpg")
        duplicate = tmp_path / "scroll-copy.jpg"
        shutil.copyfile(first, duplicate)
        view = DuplicateManagerView(tmp_path / "not-created.db", Config(tmp_path / "small-config"))
        report = DuplicateScanService([_wallpaper(first, 1), _wallpaper(duplicate, 2)]).scan()
        view._report = report
        view._candidate_by_id = {candidate.wallpaper_id: candidate for candidate in report.candidates}
        view._render_report()
        view.resize(560, 420)
        view.show()
        qapp.processEvents()
        try:
            assert view.tabs.isVisible()
            assert not view.delete_button.isEnabled()
            scrollbar = view.exact_tab.results_scroll.verticalScrollBar()
            assert scrollbar.maximum() > 0
            scrollbar.setValue(scrollbar.maximum())
            qapp.processEvents()
            assert scrollbar.value() == scrollbar.maximum()
        finally:
            view.close()

    def test_scan_worker_reports_progress_and_complete_groups(self, qapp, tmp_path: Path) -> None:
        first = _make_image(tmp_path / "worker-first.jpg")
        duplicate = tmp_path / "worker-copy.jpg"
        shutil.copyfile(first, duplicate)
        database = Database(tmp_path / "worker-library.db")
        database.connect()
        repository = WallpaperRepository(database)
        repository.add(_wallpaper(first, 1))
        repository.add(_wallpaper(duplicate, 2))
        view = DuplicateManagerView(database.path, Config(tmp_path / "worker-config"))
        progress = []
        view._on_scan_progress = lambda done, total, state: progress.append((done, total, state))
        try:
            view.start_scan()
            for _ in range(400):
                qapp.processEvents()
                if view._report is not None and view._scan_worker is None:
                    break
                QTest.qWait(20)
            assert view._report is not None and view._report.completed
            assert len(view._report.exact_groups) == 1
            assert progress and progress[-1][:2] == (2, 2)
            assert view._scan_worker is None
            assert not view.delete_button.isEnabled()
        finally:
            view.shutdown()
            view.close()
            database.close()

    def test_scan_cancel_control_discards_incomplete_worker_result(
        self, qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class WaitingWorker(QThread):
            progress = Signal(int, int, str)
            report_ready = Signal(object)
            failed = Signal(str)

            def __init__(self, _database_path, _threshold, parent=None):
                super().__init__(parent)
                self.cancelled = threading.Event()

            def cancel(self) -> None:
                self.cancelled.set()

            def run(self) -> None:
                self.progress.emit(0, 1, "Reading library snapshot")
                self.cancelled.wait(5)
                self.report_ready.emit(None)

        monkeypatch.setattr(duplicate_ui_module, "DuplicateScanWorker", WaitingWorker)
        view = DuplicateManagerView(tmp_path / "cancel.db", Config(tmp_path / "cancel-config"))
        view.show()
        try:
            view.start_scan()
            QTest.qWait(50)
            assert view.cancel_button.isEnabled()
            QTest.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
            for _ in range(100):
                qapp.processEvents()
                if view._scan_worker is None:
                    break
                QTest.qWait(20)
            assert view._scan_worker is None
            assert view._report is None
            assert "cancelled" in view.scan_summary.text().casefold()
            assert "partial results were discarded" in view.scan_summary.text()
        finally:
            view.shutdown()
            view.close()

    def test_compare_and_preview_selections_are_independent_and_read_only(
        self, qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = _make_image(tmp_path / "first.jpg")
        duplicate = tmp_path / "duplicate.jpg"
        shutil.copyfile(first, duplicate)
        report = DuplicateScanService([_wallpaper(first, 1), _wallpaper(duplicate, 2)]).scan()
        group = _group_for(report, "exact")
        view = DuplicateManagerView(tmp_path / "readonly.db", Config(tmp_path / "choice-config"))
        view._report = report
        view._candidate_by_id = {candidate.wallpaper_id: candidate for candidate in report.candidates}
        view._render_report()
        view.show()
        qapp.processEvents()
        cards = view.exact_tab.contents.findChildren(duplicate_ui_module.DuplicateGroupCard)
        members = cards[0].findChildren(duplicate_ui_module.MemberChoice)
        members_by_id = {member._candidate.wallpaper_id: member for member in members}
        first_member = members_by_id[group.members[0].wallpaper_id]
        second_member = members_by_id[group.members[1].wallpaper_id]
        keep_id = group.members[0].wallpaper_id
        remove_id = group.members[1].wallpaper_id

        class DialogStub:
            selected = ()

            def __init__(self, candidates, _parent, **_roles):
                DialogStub.selected = tuple(candidates)

            def exec(self):
                return 1

        monkeypatch.setattr(duplicate_ui_module, "ComparisonDialog", DialogStub)
        try:
            QTest.mouseClick(first_member.compare_check, Qt.MouseButton.LeftButton)
            QTest.mouseClick(second_member.compare_check, Qt.MouseButton.LeftButton)
            QTest.mouseClick(first_member.remove_check, Qt.MouseButton.LeftButton)
            QTest.mouseClick(first_member.keep_radio, Qt.MouseButton.LeftButton)
            QTest.mouseClick(second_member.remove_check, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert view._compare_ids == {1, 2}
            assert view._removals[group.group_id] == {remove_id}
            assert view._keeps[group.group_id] == keep_id
            assert not first_member.remove_check.isChecked()
            assert view.compare_button.isEnabled()
            view.compare_selected()
            assert len(DialogStub.selected) == 2

            before = {path: path.read_bytes() for path in (first, duplicate)}
            received = []
            view._show_preview = received.append
            view.preview_selected()
            for _ in range(100):
                qapp.processEvents()
                if received:
                    break
                QTest.qWait(20)
            assert received
            assert received[0].files_selected == 1
            assert first.read_bytes() == before[first]
            assert duplicate.read_bytes() == before[duplicate]
        finally:
            view.shutdown()
            view.close()
