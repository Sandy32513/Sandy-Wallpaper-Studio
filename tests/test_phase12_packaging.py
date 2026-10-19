"""Windowed-launch and first-run packaging support checks."""

from __future__ import annotations

import argparse
import ctypes
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.utils import logging_config


def test_windowed_version_action_reports_the_version_in_a_native_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    messages: list[tuple[object, ...]] = []

    class FakeUser32:
        @staticmethod
        def MessageBoxW(*args: object) -> int:
            messages.append(args)
            return 1

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=FakeUser32()), raising=False)
    monkeypatch.setattr(main_module.sys, "stdout", None)
    monkeypatch.setattr(main_module.sys, "platform", "win32")
    parser = argparse.ArgumentParser()
    action = main_module._VersionAction(option_strings=["--version"], dest="version", nargs=0)

    with pytest.raises(SystemExit) as error:
        action(parser, argparse.Namespace(), None)

    assert error.value.code == 0
    assert messages and str(messages[0][1]).endswith("0.7.0-dev")


def test_windowed_logging_keeps_file_diagnostics_without_console(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    try:
        monkeypatch.setattr(logging_config.sys, "stderr", None)
        active = logging_config.setup_logging(tmp_path / "Logs", file_enabled=True)

        assert active
        app_handlers = [handler for handler in root_logger.handlers if getattr(handler, "_sandy_app_handler", False)]
        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.handlers.RotatingFileHandler)
        logging.getLogger("packaging.smoke").error("windowed startup diagnostic")
        app_handlers[0].flush()
        assert "windowed startup diagnostic" in (tmp_path / "Logs" / "app.log").read_text(encoding="utf-8")
    finally:
        for handler in list(root_logger.handlers):
            if getattr(handler, "_sandy_app_handler", False):
                root_logger.removeHandler(handler)
                handler.close()
        root_logger.handlers[:] = original_handlers


def test_windowed_gui_startup_failure_is_logged_and_returns_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PySide6 import QtWidgets

    import app.database as database_module
    import app.main as main_module
    import app.ui.main_window as main_window_module

    class FakeConfig:
        config_dir = tmp_path
        logs_dir = tmp_path / "Logs"

        def __init__(self, config_dir: Path) -> None:
            self.config_dir = config_dir
            self.logs_dir = config_dir / "Logs"

        @property
        def database_path(self) -> Path:
            return self.config_dir / "wallpapers.db"

        def load(self) -> None:
            return None

        def save(self) -> None:
            return None

        def get(self, key: str, default: object = None) -> object:
            return default

    class FakeDatabase:
        path = tmp_path / "wallpapers.db"

        def __init__(self, _path: Path) -> None:
            self.closed = False

        def connect(self) -> None:
            return None

        def close(self) -> None:
            self.closed = True

    class FakeCategoryRepository:
        def __init__(self, _db: FakeDatabase) -> None:
            return None

        def seed_defaults(self) -> None:
            return None

    class FakeApplication:
        def __init__(self, _argv: list[str]) -> None:
            return None

        @staticmethod
        def instance() -> None:
            return None

        def setAttribute(self, *_args: object) -> None:
            return None

        def setApplicationName(self, *_args: object) -> None:
            return None

        def setApplicationVersion(self, *_args: object) -> None:
            return None

        def setOrganizationName(self, *_args: object) -> None:
            return None

    class FailedWindow:
        def __init__(self, **_kwargs: object) -> None:
            raise RuntimeError("synthetic GUI startup failure")

    databases: list[FakeDatabase] = []

    def create_database(path: Path) -> FakeDatabase:
        database = FakeDatabase(path)
        databases.append(database)
        return database

    monkeypatch.setattr(main_module, "_parse_args", lambda: SimpleNamespace(debug=False, library=str(tmp_path)))
    monkeypatch.setattr(main_module, "Config", FakeConfig)
    monkeypatch.setattr(main_module, "_ensure_directory_structure", lambda _config: None)
    monkeypatch.setattr(main_module, "setup_logging", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(database_module, "Database", create_database)
    monkeypatch.setattr(database_module, "CategoryRepository", FakeCategoryRepository)
    monkeypatch.setattr(QtWidgets, "QApplication", FakeApplication)
    monkeypatch.setattr(main_window_module, "MainWindow", FailedWindow)
    monkeypatch.setattr(main_module.sys, "stdout", None)

    assert main_module.main() == 1
    assert len(databases) == 1
    assert databases[0].closed


def test_native_wallpaper_api_boundary_is_mocked_for_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from PIL import Image

    from app.services import wallpaper_service

    image_path = tmp_path / "temporary-wallpaper.png"
    Image.new("RGB", (32, 24), (12, 34, 56)).save(image_path)

    class FakeUser32:
        def __init__(self, result: int) -> None:
            self.result = result
            self.calls: list[tuple[object, ...]] = []

        def SystemParametersInfoW(self, *args: object) -> int:
            self.calls.append(args)
            return self.result

    success_api = FakeUser32(1)
    monkeypatch.setattr(wallpaper_service.ctypes, "windll", SimpleNamespace(user32=success_api), raising=False)
    successful = wallpaper_service.WindowsWallpaperService(simulate=False)
    successful._set_style_registry = lambda _style: None  # type: ignore[method-assign]
    assert successful.set_wallpaper(image_path, style="Fill")
    assert success_api.calls == [
        (
            wallpaper_service.SPI_SETDESKWALLPAPER,
            0,
            str(image_path.resolve()),
            wallpaper_service.SPIF_UPDATEINIFILE | wallpaper_service.SPIF_SENDCHANGE,
        )
    ]
    assert successful.get_current_wallpaper() == str(image_path.resolve())

    failure_api = FakeUser32(0)
    monkeypatch.setattr(wallpaper_service.ctypes, "windll", SimpleNamespace(user32=failure_api), raising=False)
    monkeypatch.setattr(wallpaper_service.ctypes, "GetLastError", lambda: 5, raising=False)
    failing = wallpaper_service.WindowsWallpaperService(simulate=False)
    failing._set_style_registry = lambda _style: None  # type: ignore[method-assign]
    with pytest.raises(wallpaper_service.WallpaperServiceError, match="error code: 5"):
        failing.set_wallpaper(image_path, style="Fill")
    assert failure_api.calls
    assert failing._history_stack == []


def test_packaged_runtime_check_imports_image_and_persists_settings_across_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import app.main as main_module
    from app.config import Config
    from app.database import Database

    profile = tmp_path / "isolated profile with spaces"
    config = Config(profile)
    config.load()
    config.save()
    database = Database(config.database_path)
    database.connect()

    assert main_module._prepare_packaged_runtime_check(config, database) == 0
    assert "Prepare check passed" in capsys.readouterr().out

    # Recreate both objects as a new application process would.
    restarted_config = Config(profile)
    restarted_config.load()
    restarted_database = Database(restarted_config.database_path)
    restarted_database.connect()
    imported_path = restarted_config.temp_dir / "sws-packaged-import-input" / "sws-runtime-import.png"
    assert restarted_config.get("theme") == "light"
    assert imported_path.is_file()

    assert main_module._validate_packaged_runtime(restarted_config, restarted_database) == 0
    report = capsys.readouterr().out
    assert "Runtime check passed" in report
    assert "persisted setting" in report
