"""End-to-end UI checks for review, cleanup confirmation, and navigation."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMessageBox, QTextBrowser

from app.config import Config
from app.database.database import Database
from app.database.models import Wallpaper
from app.services import duplicate_cleanup_service, duplicate_scan_worker
from app.services.duplicate_scan_service import DuplicateScanService
from app.ui import duplicate_manager_view
from app.ui.main_window import MainWindow


def _image(path: Path, color: tuple[int, int, int] = (32, 88, 144)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (72, 48), color).save(path, format="JPEG", quality=91)
    return path


def _wallpaper(path: Path, wallpaper_id: int) -> Wallpaper:
    return Wallpaper(
        id=wallpaper_id,
        filename=path.name,
        path=str(path),
        title=path.stem,
        width=72,
        height=48,
        file_size=path.stat().st_size,
    )


def _prepared_view(qapp, tmp_path: Path):
    library = tmp_path / "isolated-library"
    keep_path = _image(library / "keep.jpg")
    target_path = library / "target.jpg"
    shutil.copyfile(keep_path, target_path)
    report = DuplicateScanService(
        [_wallpaper(keep_path, 1), _wallpaper(target_path, 2)]
    ).scan()
    group = report.exact_groups[0]

    config = Config(tmp_path / "isolated-config")
    config.set("library_path", str(library))
    view = duplicate_manager_view.DuplicateManagerView(tmp_path / "isolated.db", config)
    view._report = report
    view._candidate_by_id = {
        candidate.wallpaper_id: candidate for candidate in report.candidates
    }
    view._keeps[group.group_id] = group.members[0].wallpaper_id
    view._removals[group.group_id] = {group.members[1].wallpaper_id}
    view._render_report()
    view._update_action_buttons()
    return view, group, keep_path, target_path


def _wait_until(qapp, predicate) -> None:
    for _ in range(500):
        qapp.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    raise AssertionError("The duplicate cleanup workflow did not finish in time.")


def test_large_exact_group_member_pagination_preserves_selection(qapp, tmp_path: Path) -> None:
    library = tmp_path / "paged-library"
    keep_path = _image(library / "a-keep.jpg")
    paths = [keep_path]
    for index in range(2, 14):
        copy = library / f"copy-{index:02d}.jpg"
        shutil.copyfile(keep_path, copy)
        paths.append(copy)
    report = DuplicateScanService(
        [_wallpaper(path, index) for index, path in enumerate(paths, start=1)]
    ).scan()
    group = report.exact_groups[0]
    keep_id = group.members[0].wallpaper_id
    target_id = group.members[-1].wallpaper_id

    config = Config(tmp_path / "paged-config")
    config.set("library_path", str(library))
    view = duplicate_manager_view.DuplicateManagerView(tmp_path / "paged.db", config)
    view._report = report
    view._candidate_by_id = {
        candidate.wallpaper_id: candidate for candidate in report.candidates
    }
    view._keeps[group.group_id] = keep_id
    view._removals[group.group_id] = {target_id}
    view._render_report()
    view.show()
    qapp.processEvents()
    card = view.exact_tab.findChildren(duplicate_manager_view.DuplicateGroupCard)[0]

    try:
        visible_members = [
            member
            for member in card.findChildren(duplicate_manager_view.MemberChoice)
            if member.isVisible()
        ]
        assert len(visible_members) == 12
        QTest.mouseClick(card.member_next, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        visible_members = [
            member
            for member in card.findChildren(duplicate_manager_view.MemberChoice)
            if member.isVisible()
        ]
        assert len(visible_members) == 1
        assert visible_members[0]._candidate.wallpaper_id == target_id
        assert visible_members[0].remove_check.isChecked()
        assert "page 2/2" in card.member_page_label.text()

        QTest.mouseClick(card.member_previous, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        visible_members = [
            member
            for member in card.findChildren(duplicate_manager_view.MemberChoice)
            if member.isVisible()
        ]
        assert len(visible_members) == 12
        assert any(
            member._candidate.wallpaper_id == keep_id and member.keep_radio.isChecked()
            for member in visible_members
        )
    finally:
        view.shutdown()
        view.close()


def test_cleanup_confirmation_cancel_preserves_all_files_and_shows_full_review(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    view, group, keep_path, target_path = _prepared_view(qapp, tmp_path)
    before = (keep_path.read_bytes(), target_path.read_bytes())
    dialogs = []

    def reject_confirmation(dialog):
        dialogs.append(dialog)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(duplicate_manager_view, "windows_recycle_bin_available", lambda: True)
    monkeypatch.setattr(
        duplicate_manager_view.CleanupConfirmationDialog,
        "exec",
        reject_confirmation,
    )
    view.status_message.connect(lambda _message: None)
    try:
        view.cleanup_selected()
        _wait_until(qapp, lambda: view._preview_worker is None)

        assert len(dialogs) == 1
        details = dialogs[0].findChild(QTextBrowser).toPlainText()
        assert str(keep_path) in details
        assert str(target_path) in details
        assert "exact duplicate" in details
        assert dialogs[0].cancel_button.isDefault()
        assert not dialogs[0].confirm_button.isDefault()
        assert view._keeps[group.group_id] == group.members[0].wallpaper_id
        assert (keep_path.read_bytes(), target_path.read_bytes()) == before
        assert "cancelled" in view.progress.format().casefold()
    finally:
        view.shutdown()
        view.close()


def test_approved_ui_cleanup_uses_injected_disposable_recycler(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    view, _group, keep_path, target_path = _prepared_view(qapp, tmp_path)
    confirmed_dialogs = []
    messages = []
    warnings = []

    def accept_confirmation(dialog):
        confirmed_dialogs.append(dialog)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(duplicate_manager_view, "windows_recycle_bin_available", lambda: True)
    monkeypatch.setattr(
        duplicate_manager_view.CleanupConfirmationDialog,
        "exec",
        accept_confirmation,
    )
    def acknowledge_message(message):
        messages.append((message.text(), message.informativeText()))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", acknowledge_message)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )

    def test_only_recycler(report, preview, allowed_root, cancel_event=None, progress=None):
        return duplicate_cleanup_service.execute_cleanup(
            report,
            preview,
            allowed_root,
            cancel_event=cancel_event,
            progress=progress,
            recycler=lambda path: path.unlink(),
            lock_check=lambda _path: None,
        )

    monkeypatch.setattr(duplicate_scan_worker, "execute_cleanup", test_only_recycler)
    try:
        view.cleanup_selected()
        _wait_until(
            qapp,
            lambda: view._preview_worker is None and view._cleanup_worker is None,
        )

        assert len(confirmed_dialogs) == 1
        assert "Move selected files to Recycle Bin" in confirmed_dialogs[0].confirm_button.text()
        assert not target_path.exists(), (messages, warnings)
        assert keep_path.exists()
        assert view._report is None
        assert "new scan" in view.scan_summary.text().casefold()
    finally:
        view.shutdown()
        view.close()


def test_fresh_main_window_navigates_all_destinations_without_external_actions(
    qapp, tmp_path: Path
) -> None:
    database = Database(tmp_path / "fresh-app.db")
    database.connect()
    window = MainWindow(Config(tmp_path / "fresh-config"), database)
    window.show()
    qapp.processEvents()
    destinations = (
        "dashboard",
        "library",
        "favorites",
        "history",
        "settings",
        "duplicates",
        "discover",
        "categories",
        "downloads",
    )
    try:
        assert window._stack.currentWidget() is window._views["dashboard"]
        assert window._rotation_scheduler.state == "disabled"
        for key in destinations:
            QTest.mouseClick(window._sidebar._buttons[key], Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert window._stack.currentWidget() is window._views[key]
    finally:
        window.close()
