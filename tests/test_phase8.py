"""Phase 8 tests for automatic wallpaper rotation."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtTest import QTest

from app.config import Config, RotationPreferences
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.migrations import _migration_001_initial_schema
from app.database.models import Wallpaper, WallpaperHistory
from app.database.wallpaper_repository import WallpaperRepository
from app.services.rotation_scheduler import RotationScheduler
from app.services.rotation_service import RotationResult, RotationService
from app.services.wallpaper_service import WindowsWallpaperService
from app.ui.components.wallpaper_card import WallpaperCard
from app.ui.history_view import HistoryView
from app.ui.main_window import MainWindow
from app.ui.rotation_view import RotationSettingsView
from app.ui.settings_view import SettingsView


@pytest.fixture
def phase8_db(tmp_path: Path):
    db = Database(tmp_path / "phase8.db")
    db.connect()
    CategoryRepository(db).seed_defaults()
    yield db
    db.close()


def _image(path: Path, size: tuple[int, int] = (1920, 1080)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(80, 120, 180)).save(path, format="JPEG")
    return path


def _add_wallpaper(
    db: Database,
    path: Path,
    *,
    category: str = "Nature",
    width: int = 1920,
    height: int = 1080,
) -> Wallpaper:
    wallpaper = Wallpaper(
        filename=path.name,
        path=str(path),
        title=path.stem,
        category=category,
        width=width,
        height=height,
        resolution_class="1080p",
    )
    wallpaper.id = WallpaperRepository(db).add(wallpaper)
    return wallpaper


def _rotation_service(db: Database, order=None):
    wallpaper_repository = WallpaperRepository(db)
    history_repository = HistoryRepository(db)
    wallpaper_service = WindowsWallpaperService(
        db=db,
        wallpaper_repo=wallpaper_repository,
        history_repo=history_repository,
        simulate=True,
    )
    service = RotationService(
        wallpaper_repository,
        wallpaper_service,
        history_repository,
        candidate_order=order,
    )
    return service, wallpaper_service, history_repository


def _preferences(**overrides) -> RotationPreferences:
    values = {
        "enabled": True,
        "interval_minutes": 15,
        "random_selection": False,
    }
    values.update(overrides)
    return RotationPreferences(**values)


class TestRotationConfiguration:
    def test_initial_disabled_state_and_interval_defaults(self, tmp_path: Path) -> None:
        config = Config(tmp_path)
        assert config.rotation_preferences.enabled is False
        assert config.rotation_preferences.interval_minutes == 60

    def test_interval_bounds_and_filter_validation(self) -> None:
        assert RotationPreferences(interval_minutes=1).interval_minutes == 1
        assert RotationPreferences(interval_minutes=10_080).interval_minutes == 10_080
        for value in (0, 10_081, True, "60"):
            with pytest.raises(ValueError):
                RotationPreferences(interval_minutes=value)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            RotationPreferences(min_width=-1)
        with pytest.raises(ValueError):
            RotationPreferences(categories=("Nature", ""))

    def test_preferences_persist_and_restore(self, tmp_path: Path) -> None:
        config = Config(tmp_path)
        preferences = _preferences(
            interval_minutes=90,
            random_selection=True,
            categories=("Nature", "Space"),
            min_width=2560,
            min_height=1440,
        )
        config.set_rotation_preferences(preferences)
        config.save()

        restored = Config(tmp_path)
        restored.load()
        assert restored.rotation_preferences == preferences

    def test_legacy_interval_and_invalid_values_fall_back_safely(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            json.dumps({"rotation_interval": "2 hours", "rotation_min_width": "wide"}),
            encoding="utf-8",
        )
        config = Config(tmp_path)
        config.load()
        assert config.rotation_preferences.interval_minutes == 120
        assert config.rotation_preferences.min_width == 0


class TestRotationSelection:
    def test_empty_library_is_reported_without_history(self, phase8_db: Database) -> None:
        service, _, history = _rotation_service(phase8_db)
        result = service.rotate_once(_preferences())
        assert not result.success
        assert result.error == "NO_CANDIDATES"
        assert history.count() == 0

    def test_category_and_boundary_resolution_filters(self, phase8_db: Database, tmp_path: Path) -> None:
        nature = _add_wallpaper(
            phase8_db,
            _image(tmp_path / "nature.jpg", (2560, 1440)),
            width=2560,
            height=1440,
        )
        _add_wallpaper(
            phase8_db, _image(tmp_path / "small.jpg", (1920, 1080)), width=1920, height=1080
        )
        _add_wallpaper(
            phase8_db,
            _image(tmp_path / "space.jpg", (3840, 2160)),
            category="Space",
            width=3840,
            height=2160,
        )

        candidates = WallpaperRepository(phase8_db).get_rotation_candidates(
            categories=("Nature",), min_width=2560, min_height=1440
        )
        assert [candidate.id for candidate in candidates] == [nature.id]

    def test_missing_resolution_metadata_does_not_bypass_minimum(self, phase8_db: Database, tmp_path: Path) -> None:
        _add_wallpaper(
            phase8_db,
            _image(tmp_path / "unknown.jpg"),
            width=0,
            height=0,
        )
        assert WallpaperRepository(phase8_db).get_rotation_candidates(
            min_width=1, min_height=1
        ) == []
        assert len(WallpaperRepository(phase8_db).get_rotation_candidates()) == 1

    def test_no_category_match_is_not_silently_relaxed(self, phase8_db: Database, tmp_path: Path) -> None:
        _add_wallpaper(phase8_db, _image(tmp_path / "nature.jpg"), category="Nature")
        service, _, _ = _rotation_service(phase8_db)
        result = service.rotate_once(_preferences(categories=("Space",)))
        assert result.error == "NO_CANDIDATES"

    def test_missing_corrupt_and_unsupported_files_are_skipped(self, phase8_db: Database, tmp_path: Path) -> None:
        _add_wallpaper(phase8_db, tmp_path / "missing.jpg")
        corrupt_path = tmp_path / "corrupt.jpg"
        corrupt_path.write_text("not an image", encoding="utf-8")
        _add_wallpaper(phase8_db, corrupt_path)
        unsupported_path = tmp_path / "unsupported.gif"
        unsupported_path.write_bytes(b"GIF89a")
        _add_wallpaper(phase8_db, unsupported_path)
        valid = _add_wallpaper(phase8_db, _image(tmp_path / "valid.jpg"))
        service, _, _ = _rotation_service(phase8_db)

        result = service.rotate_once(_preferences())
        assert result.success
        assert result.wallpaper_id == valid.id

    def test_deterministic_cycle_avoids_previous_and_wraps(self, phase8_db: Database, tmp_path: Path) -> None:
        first = _add_wallpaper(phase8_db, _image(tmp_path / "first.jpg"))
        second = _add_wallpaper(phase8_db, _image(tmp_path / "second.jpg"))
        service, _, _ = _rotation_service(phase8_db)

        one = service.rotate_once(_preferences())
        two = service.rotate_once(_preferences())
        three = service.rotate_once(_preferences())
        assert [one.wallpaper_id, two.wallpaper_id, three.wallpaper_id] == [
            first.id,
            second.id,
            first.id,
        ]

    def test_only_wallpaper_can_repeat_when_it_is_the_only_eligible_choice(
        self, phase8_db: Database, tmp_path: Path
    ) -> None:
        only = _add_wallpaper(phase8_db, _image(tmp_path / "only.jpg"))
        service, _, _ = _rotation_service(phase8_db)
        assert service.rotate_once(_preferences()).wallpaper_id == only.id
        assert service.rotate_once(_preferences()).wallpaper_id == only.id

    def test_random_order_is_injectable_for_deterministic_tests(
        self, phase8_db: Database, tmp_path: Path
    ) -> None:
        _add_wallpaper(phase8_db, _image(tmp_path / "first.jpg"))
        second = _add_wallpaper(phase8_db, _image(tmp_path / "second.jpg"))
        service, _, _ = _rotation_service(phase8_db, order=lambda candidates: list(reversed(candidates)))
        result = service.rotate_once(_preferences(random_selection=True))
        assert result.wallpaper_id == second.id

    def test_library_changes_are_seen_on_next_rotation(self, phase8_db: Database, tmp_path: Path) -> None:
        service, _, _ = _rotation_service(phase8_db)
        assert service.rotate_once(_preferences()).error == "NO_CANDIDATES"
        added = _add_wallpaper(phase8_db, _image(tmp_path / "added.jpg"))
        assert service.rotate_once(_preferences()).wallpaper_id == added.id

    def test_cancellation_prevents_wallpaper_application(self, phase8_db: Database, tmp_path: Path) -> None:
        _add_wallpaper(phase8_db, _image(tmp_path / "wallpaper.jpg"))
        service, wallpaper_service, _ = _rotation_service(phase8_db)
        applied: list[int] = []
        wallpaper_service.set_selected_wallpaper = lambda wallpaper, **kwargs: applied.append(  # type: ignore[method-assign]
            wallpaper.id
        )
        cancelled = Event()
        cancelled.set()
        result = service.rotate_once(_preferences(), cancellation=cancelled)
        assert result.error == "CANCELLED"
        assert applied == []


class TestRotationHistory:
    def test_success_records_one_rotation_history_entry(self, phase8_db: Database, tmp_path: Path) -> None:
        wallpaper = _add_wallpaper(phase8_db, _image(tmp_path / "wallpaper.jpg"))
        service, _, history = _rotation_service(phase8_db)
        result = service.rotate_once(_preferences())
        events = history.get_recent_rotation_events()
        assert result.success
        assert len(events) == 1
        assert events[0][0].wallpaper_id == wallpaper.id
        assert events[0][0].source == "rotation"
        assert events[0][0].success is True
        assert history.count() == 1

    def test_failed_apply_is_audited_but_not_reported_as_applied(
        self, phase8_db: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wallpaper = _add_wallpaper(phase8_db, _image(tmp_path / "wallpaper.jpg"))
        service, wallpaper_service, history = _rotation_service(phase8_db)

        def fail_apply(*args, **kwargs):
            raise OSError("desktop API unavailable")

        monkeypatch.setattr(wallpaper_service, "set_selected_wallpaper", fail_apply)
        result = service.rotate_once(_preferences())
        events = history.get_recent_rotation_events()
        assert not result.success
        assert history.count() == 0
        assert len(events) == 1
        assert events[0][0].success is False
        assert "desktop API unavailable" in events[0][0].error_message
        assert events[0][0].wallpaper_id == wallpaper.id

    def test_rotation_recovers_after_a_failed_application(
        self, phase8_db: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wallpaper = _add_wallpaper(phase8_db, _image(tmp_path / "wallpaper.jpg"))
        service, wallpaper_service, history = _rotation_service(phase8_db)
        apply = wallpaper_service.set_selected_wallpaper
        calls = 0

        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("temporary desktop error")
            return apply(*args, **kwargs)

        monkeypatch.setattr(wallpaper_service, "set_selected_wallpaper", fail_once)
        failed = service.rotate_once(_preferences())
        succeeded = service.rotate_once(_preferences())
        assert not failed.success
        assert succeeded.success
        assert succeeded.wallpaper_id == wallpaper.id
        assert history.count() == 1
        assert len(history.get_recent_rotation_events()) == 2

    def test_failed_attempt_does_not_change_repeat_avoidance_or_previous_restore(
        self, phase8_db: Database, tmp_path: Path
    ) -> None:
        first = _add_wallpaper(phase8_db, _image(tmp_path / "first.jpg"))
        second = _add_wallpaper(phase8_db, _image(tmp_path / "second.jpg"))
        history = HistoryRepository(phase8_db)
        history.add(
            WallpaperHistory(
                wallpaper_id=first.id,
                set_at=datetime.now(UTC).isoformat(),
                source="rotation",
                success=True,
            )
        )
        history.add(
            WallpaperHistory(
                wallpaper_id=second.id,
                set_at=datetime.now(UTC).isoformat(),
                source="rotation",
                success=False,
                error_message="failed",
            )
        )
        assert history.get_latest().wallpaper_id == first.id
        service, _, _ = _rotation_service(phase8_db)
        assert service.rotate_once(_preferences()).wallpaper_id == second.id

    def test_existing_history_is_preserved_by_rotation_migration(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy.db"
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        _migration_001_initial_schema(cursor)
        cursor.execute(
            "INSERT INTO wallpapers (filename, path, title) VALUES ('old.jpg', 'old.jpg', 'Old')"
        )
        cursor.execute(
            "INSERT INTO wallpaper_history (wallpaper_id, set_at, monitor) "
            "VALUES (1, '2026-10-18T12:00:00Z', 'DISPLAY1')"
        )
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at, description) "
            "VALUES (1, '2026-10-18T12:00:00Z', 'Initial schema')"
        )
        connection.commit()
        connection.close()

        db = Database(db_path)
        db.connect()
        try:
            row = HistoryRepository(db).get_latest()
            assert row is not None
            assert row.source == "manual"
            assert row.success is True
            assert row.error_message == ""
            assert db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 2
        finally:
            db.close()


class TestRotationSchedulerAndUI:
    def test_start_pause_resume_stop_and_repeated_start_use_one_timer(
        self, qapp, phase8_db: Database
    ) -> None:
        monotonic = [100.0]
        wall_now = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
        scheduler = RotationScheduler(
            phase8_db.path,
            clock=lambda: monotonic[0],
            wall_clock=lambda: wall_now,
        )
        try:
            timer = scheduler._timer
            scheduler.start(_preferences())
            first_deadline = scheduler.next_rotation_at
            scheduler.start(_preferences())
            assert scheduler.state == "running"
            assert scheduler.timer_active
            assert scheduler._timer is timer
            assert scheduler.next_rotation_at == first_deadline

            scheduler.pause()
            assert scheduler.state == "paused"
            assert not scheduler.timer_active
            monotonic[0] += 30
            scheduler.resume()
            assert scheduler.state == "running"
            assert scheduler.timer_active
            assert scheduler.remaining_seconds == pytest.approx(900)

            scheduler.stop()
            assert scheduler.state == "stopped"
            assert not scheduler.timer_active
        finally:
            scheduler.shutdown()

    def test_shutdown_cancels_the_timer(self, qapp, phase8_db: Database) -> None:
        scheduler = RotationScheduler(phase8_db.path)
        scheduler.start(_preferences())
        assert scheduler.timer_active
        scheduler.shutdown()
        assert scheduler.state == "stopped"
        assert not scheduler.timer_active

    def test_pause_after_deadline_resumes_with_full_interval(self, qapp, phase8_db: Database) -> None:
        monotonic = [0.0]
        scheduler = RotationScheduler(phase8_db.path, clock=lambda: monotonic[0])
        try:
            scheduler.start(_preferences(interval_minutes=1))
            monotonic[0] = 60.0
            scheduler.pause()
            scheduler.resume()
            assert scheduler.remaining_seconds == pytest.approx(60)
        finally:
            scheduler.shutdown()

    def test_settings_view_updates_preferences_and_state(self, qapp, phase8_db: Database, tmp_path: Path) -> None:
        config = Config(tmp_path / "config")
        scheduler = RotationScheduler(phase8_db.path)
        view = RotationSettingsView(config, phase8_db, scheduler)
        try:
            view.resize(800, 600)
            view.show()
            qapp.processEvents()
            view._interval.setValue(5)
            QTest.mouseClick(
                view._enabled,
                Qt.MouseButton.LeftButton,
                pos=QPoint(10, view._enabled.height() // 2),
            )
            QTest.mouseClick(view._apply_button, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert config.rotation_preferences.enabled
            assert config.rotation_preferences.interval_minutes == 5
            assert scheduler.state == "running"
            assert view._status_label.text() == "Automatic rotation is running."
            assert view._pause_button.isEnabled()

            QTest.mouseClick(view._pause_button, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert view._status_label.text() == "Automatic rotation is paused."
            assert view._resume_button.isEnabled()

            QTest.mouseClick(view._resume_button, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert scheduler.state == "running"
            assert view._status_label.text() == "Automatic rotation resumed."

            QTest.mouseClick(view._stop_button, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert scheduler.state == "stopped"
            assert not scheduler.timer_active
        finally:
            scheduler.shutdown()
            view.close()

    def test_settings_keyboard_focus_order_includes_categories_and_controls(
        self, qapp, phase8_db: Database, tmp_path: Path
    ) -> None:
        scheduler = RotationScheduler(phase8_db.path)
        view = RotationSettingsView(Config(tmp_path / "focus-config"), phase8_db, scheduler)
        try:
            view.resize(720, 520)
            view.show()
            qapp.processEvents()
            focus_order = [
                view._enabled,
                view._interval,
                view._random,
                view._min_width,
                view._min_height,
                *view._category_checks.values(),
                view._apply_button,
            ]
            assert all(widget.accessibleName() for widget in focus_order)
            focus_order[0].setFocus()
            qapp.processEvents()
            assert focus_order[0].hasFocus()

            for expected in focus_order[1:]:
                focused = qapp.focusWidget()
                assert focused is not None
                QTest.keyClick(focused, Qt.Key.Key_Tab)
                qapp.processEvents()
                assert qapp.focusWidget() is expected

            # Start so the enabled Pause and Stop controls enter the focus sequence.
            view._enabled.setChecked(True)
            QTest.mouseClick(view._apply_button, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            view._apply_button.setFocus()
            QTest.keyClick(view._apply_button, Qt.Key.Key_Tab)
            qapp.processEvents()
            assert qapp.focusWidget() is view._pause_button
            QTest.keyClick(view._pause_button, Qt.Key.Key_Tab)
            qapp.processEvents()
            assert qapp.focusWidget() is view._stop_button
        finally:
            scheduler.shutdown()
            view.close()

    def test_wallpaper_card_thumbnail_click_emits_detail_request(self, qapp, tmp_path: Path) -> None:
        wallpaper = Wallpaper(
            id=42,
            filename="missing.jpg",
            path=str(tmp_path / "missing.jpg"),
            category="Nature",
        )
        card = WallpaperCard(wallpaper=wallpaper)
        emitted: list[int] = []
        card.detail_requested.connect(emitted.append)
        card.show()
        qapp.processEvents()
        try:
            QTest.mouseClick(
                card._thumb_label,
                Qt.MouseButton.LeftButton,
                pos=QPoint(12, card._thumb_label.height() // 2),
            )
            assert emitted == [42]
        finally:
            card.stop_loader()
            card.close()

    def test_main_window_navigation_and_rotation_history_tab_with_qtest(
        self, qapp, phase8_db: Database, tmp_path: Path
    ) -> None:
        window = MainWindow(config=Config(tmp_path / "navigation-config"), db=phase8_db)
        window.show()
        qapp.processEvents()
        try:
            QTest.mouseClick(
                window._sidebar._buttons["settings"],
                Qt.MouseButton.LeftButton,
            )
            qapp.processEvents()
            settings = window._views["settings"]
            assert window._stack.currentWidget() is settings
            assert window._sidebar._buttons["settings"]._active

            QTest.mouseClick(
                window._sidebar._buttons["history"],
                Qt.MouseButton.LeftButton,
            )
            qapp.processEvents()
            history = window._views["history"]
            assert window._stack.currentWidget() is history
            QTest.mouseClick(history._btn_tab_rotation, Qt.MouseButton.LeftButton)
            qapp.processEvents()
            assert history._stack.currentIndex() == 3
            assert history._btn_tab_rotation.isChecked()
        finally:
            window.close()

    def test_rotation_settings_remain_scrollable_at_small_sizes(
        self, qapp, phase8_db: Database, tmp_path: Path
    ) -> None:
        view = RotationSettingsView(
            Config(tmp_path / "small-view-config"),
            phase8_db,
            RotationScheduler(phase8_db.path),
        )
        try:
            view.resize(480, 360)
            view.show()
            qapp.processEvents()
            scrollbar = view._page_scroll.verticalScrollBar()
            assert scrollbar.maximum() > 0
            scrollbar.setValue(scrollbar.maximum())
            qapp.processEvents()
            assert view._apply_button.isVisible()
        finally:
            view._scheduler.shutdown()
            view.close()

    def test_disabled_startup_does_not_schedule_or_apply_wallpaper(
        self, qapp, phase8_db: Database, tmp_path: Path
    ) -> None:
        config = Config(tmp_path / "config")
        window = MainWindow(config=config, db=phase8_db)
        try:
            assert window._rotation_scheduler.state == "disabled"
            assert not window._rotation_scheduler.timer_active
            assert "settings" in window._views
            assert isinstance(window._views["settings"], SettingsView)
        finally:
            window.close()

    def test_enabled_startup_waits_for_interval_and_pause_is_runtime_only(
        self, qapp, phase8_db: Database, tmp_path: Path
    ) -> None:
        config = Config(tmp_path / "enabled-config")
        preferences = _preferences(interval_minutes=60)
        config.set_rotation_preferences(preferences)
        config.save()
        window = MainWindow(config=config, db=phase8_db)
        try:
            assert window._rotation_scheduler.state == "running"
            assert window._rotation_scheduler.timer_active
            assert HistoryRepository(phase8_db).count() == 0
            window._rotation_scheduler.pause()
            assert config.rotation_preferences.enabled is True
        finally:
            window.close()

    def test_worker_completion_is_delivered_on_qt_owner_thread(
        self, qapp, phase8_db: Database
    ) -> None:
        class CompletionThread(QThread):
            completed = Signal(object)

            def run(self) -> None:
                self.completed.emit(RotationResult(success=True, wallpaper_id=1))

        scheduler = RotationScheduler(phase8_db.path)
        threads = []
        scheduler.rotation_finished.connect(lambda _result: threads.append(QThread.currentThread()))
        worker = CompletionThread()
        worker.completed.connect(
            scheduler._on_rotation_finished
        )
        try:
            worker.start()
            assert worker.wait(2000)
            qapp.processEvents()
            assert threads == [qapp.thread()]
        finally:
            scheduler.shutdown()
            worker.deleteLater()

    def test_history_view_exposes_rotation_events_separately(
        self, qapp, phase8_db: Database, tmp_path: Path
    ) -> None:
        wallpaper = _add_wallpaper(phase8_db, _image(tmp_path / "wallpaper.jpg"))
        history = HistoryRepository(phase8_db)
        history.add(
            WallpaperHistory(
                wallpaper_id=wallpaper.id,
                set_at=datetime.now(UTC).isoformat(),
                source="rotation",
                success=False,
                error_message="test failure",
            )
        )
        wallpaper_repository = WallpaperRepository(phase8_db)
        wallpaper_service = WindowsWallpaperService(
            db=phase8_db,
            wallpaper_repo=wallpaper_repository,
            history_repo=history,
            simulate=True,
        )
        view = HistoryView(
            phase8_db,
            wallpaper_service,
            cache_dir=tmp_path / "cache",
        )
        try:
            view._switch_tab(3)
            assert view._stack.currentIndex() == 3
            assert view._rotation_layout.count() > 0
            assert view._btn_tab_rotation.text().endswith("(1)")
            assert view._history_service.count_applied() == 0
        finally:
            view.close()
