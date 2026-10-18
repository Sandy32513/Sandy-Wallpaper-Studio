"""Phase 10 configuration, operations, export, and integrated settings tests."""

from __future__ import annotations

import csv
import io
import json
import logging
import time
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QMessageBox

from app import config as config_module
from app.config import Config, RotationPreferences
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.database.models import Wallpaper
from app.database.wallpaper_repository import WallpaperRepository
from app.services import download_service as download_module
from app.services.attribution_export_service import export_attributions
from app.services.download_service import DownloadService
from app.services.duplicate_service import DuplicateService
from app.services.rotation_scheduler import RotationScheduler
from app.services.source_service import SourceService
from app.sources.base import WallpaperSearchResult
from app.ui.settings_view import SettingsView
from app.utils.hashing import compute_sha256
from app.utils.image_utils import (
    create_thumbnail,
    enforce_thumbnail_cache_limit,
    thumbnail_cache_path,
)
from app.utils.logging_config import setup_logging


@pytest.fixture
def phase10_db(tmp_path: Path):
    database = Database(tmp_path / "phase10.db")
    database.connect()
    CategoryRepository(database).seed_defaults()
    yield database
    database.close()


class TestConfigOperations:
    def test_load_validates_each_value_and_migrates_legacy_rotation(self, tmp_path: Path) -> None:
        (tmp_path / "settings.json").write_text(json.dumps({
            "max_retries": 99,
            "timeout_seconds": 42,
            "rotation_interval": "2 hours",
            "enabled_sources": ["unsupported"],
            "phash_threshold": 64,
            "wallpaper_style": [],
            "unknown": "ignored",
        }), encoding="utf-8")
        config = Config(tmp_path)
        config.load()
        assert config.get("max_retries") == 3
        assert config.get("timeout_seconds") == 42
        assert config.rotation_preferences.interval_minutes == 120
        assert config.get("enabled_sources") == ["wikimedia"]
        assert config.get("phash_threshold") == 64
        assert config.get("wallpaper_style") == "Fill"
        assert config.get("unknown") is None

    def test_validation_and_atomic_apply_failure_preserve_live_and_saved_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = Config(tmp_path)
        config.set("timeout_seconds", 42)
        config.save()
        original = (tmp_path / "settings.json").read_bytes()
        with pytest.raises(ValueError):
            config.set("max_retries", 0)

        def fail_replace(_source, _target) -> None:
            raise PermissionError("read only")

        monkeypatch.setattr(config_module.os, "replace", fail_replace)
        with pytest.raises(OSError):
            config.apply_settings({"timeout_seconds": 90})
        assert config.get("timeout_seconds") == 42
        assert (tmp_path / "settings.json").read_bytes() == original

    def test_config_snapshot_isolated(self, tmp_path: Path) -> None:
        config = Config(tmp_path)
        copy = config.snapshot()
        copy.set("phash_threshold", 20)
        assert config.get("phash_threshold") != 20


class TestSourceAndDuplicateSettings:
    def test_source_factory_applies_preferences_to_actual_search(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = Config(tmp_path)
        config.set("enabled_sources", [])
        assert SourceService.from_config(config).get_names() == []
        config.set("enabled_sources", ["wikimedia"])
        config.set("timeout_seconds", 47)
        config.set("source_result_limit", 7)
        service = SourceService.from_config(config)
        assert service.get_names() == ["wikimedia"]
        assert service._sources["wikimedia"]._timeout == 47
        assert service._result_limit == 7
        observed: dict[str, object] = {}

        def search(**kwargs):
            observed.update(kwargs)
            return []

        monkeypatch.setattr(service._sources["wikimedia"], "search", search)
        service.search("mountains", limit=50)
        assert observed["limit"] == 7
        assert observed["min_width"] == config.get("min_resolution_width")
        assert observed["min_height"] == config.get("min_resolution_height")

    def test_real_phash_threshold_changes_matches_but_never_calls_them_exact(self, phase10_db: Database) -> None:
        repo = WallpaperRepository(phase10_db)
        repo.add(Wallpaper(filename="lookalike.jpg", path="missing.jpg", sha256="not-the-query", phash="0000000000000003"))
        service = DuplicateService(phase10_db, threshold=1)
        assert service.find_near_duplicates("0000000000000000") == []
        service.threshold = 2
        matches = service.find_near_duplicates("0000000000000000")
        assert len(matches) == 1
        assert matches[0].distance == 2
        assert matches[0].match_type == "near"
        assert service.check_exact_duplicate("different-content-sha") is None
        with pytest.raises(ValueError):
            service.threshold = 65


class TestDownloadAndThumbnailSettings:
    class Response:
        def __init__(self, payload: bytes, content_type: str = "image/jpeg") -> None:
            self.payload = payload
            self.headers = {"content-type": content_type, "content-length": str(len(payload))}
            self.closed = False

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            yield self.payload

        def close(self) -> None:
            self.closed = True

    @staticmethod
    def image_payload() -> bytes:
        stream = io.BytesIO()
        Image.new("RGB", (80, 40), (20, 70, 140)).save(stream, format="JPEG")
        return stream.getvalue()

    def test_download_verifies_image_and_publishes_only_completed_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = DownloadService(tmp_path / "downloads", tmp_path / "temp")
        response = self.Response(self.image_payload())
        monkeypatch.setattr(service._session, "get", lambda *_args, **_kwargs: response)
        result = service.download(WallpaperSearchResult(
            title="Test image", width=80, height=40, file_format="jpg",
            download_url="https://example.invalid/image.jpg",
        ))
        assert result.success
        assert result.file_path and result.file_path.is_file()
        assert result.file_size == len(self.image_payload())
        assert response.closed
        assert list((tmp_path / "temp").glob("*.part")) == []

    def test_download_size_limit_rejects_before_writing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        service = DownloadService(tmp_path / "downloads", tmp_path / "temp", max_size_mb=1)
        response = self.Response(b"x" * (1024 * 1024 + 1))
        monkeypatch.setattr(service._session, "get", lambda *_args, **_kwargs: response)
        result = service.download(WallpaperSearchResult(
            title="Large", file_format="jpg", download_url="https://example.invalid/large.jpg"
        ))
        assert not result.success
        assert "maximum size" in result.error_message
        assert list((tmp_path / "downloads").rglob("*.jpg")) == []

    def test_download_retries_with_bounded_backoff_and_uses_config_factory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = Config(tmp_path / "config")
        config.set("timeout_seconds", 11)
        config.set("max_retries", 2)
        config.set("retry_backoff_factor", 2.0)
        config.set("max_simultaneous_downloads", 4)
        service = DownloadService.from_config(config)
        assert (service._timeout, service._max_retries, service._max_concurrent) == (11, 2, 4)
        response = self.Response(self.image_payload())
        attempts = 0

        def get(*_args, **_kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise download_module.requests.ConnectionError("network unavailable")
            return response

        delays: list[float] = []
        monkeypatch.setattr(service._session, "get", get)
        monkeypatch.setattr(time, "sleep", delays.append)
        result = service.download(WallpaperSearchResult(
            title="Retry", file_format="jpg", download_url="https://example.invalid/retry.jpg"
        ))
        assert result.success
        assert attempts == 2
        assert delays == [2.0]

    def test_corrupt_image_never_becomes_a_downloaded_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = DownloadService(tmp_path / "downloads", tmp_path / "temp")
        response = self.Response(b"not actually a jpeg")
        monkeypatch.setattr(service._session, "get", lambda *_args, **_kwargs: response)
        result = service.download(WallpaperSearchResult(
            title="Corrupt", file_format="jpg", download_url="https://example.invalid/corrupt.jpg"
        ))
        assert not result.success
        assert "valid image" in result.error_message
        assert list((tmp_path / "downloads").rglob("*.jpg")) == []
        assert not list((tmp_path / "temp").glob("*.part"))

    def test_cancelled_and_non_image_downloads_leave_no_partial_or_final_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = DownloadService(tmp_path / "downloads", tmp_path / "temp")
        response = self.Response(self.image_payload())
        monkeypatch.setattr(service._session, "get", lambda *_args, **_kwargs: response)
        result = service.download(
            WallpaperSearchResult(title="Cancelled", file_format="jpg", download_url="https://example.invalid/image.jpg"),
            cancelled=lambda: True,
        )
        assert not result.success
        assert result.error_message == "Download cancelled."
        assert response.closed
        assert not list((tmp_path / "downloads").rglob("*.jpg"))
        assert not list((tmp_path / "temp").glob("*.part"))

        response = self.Response(self.image_payload(), content_type="text/html")
        monkeypatch.setattr(service._session, "get", lambda *_args, **_kwargs: response)
        result = service.download(WallpaperSearchResult(
            title="Not image", file_format="jpg", download_url="https://example.invalid/page"
        ))
        assert not result.success
        assert result.error_message == "Response is not an image."
        assert response.closed
        assert not list((tmp_path / "downloads").rglob("*.jpg"))

    @pytest.mark.parametrize("kwargs", [
        {"timeout": 0}, {"max_retries": 11}, {"backoff_factor": float("inf")},
        {"max_size_mb": 0}, {"max_concurrent": 0},
    ])
    def test_download_limits_reject_invalid_constructor_values(self, tmp_path: Path, kwargs: dict) -> None:
        with pytest.raises(ValueError):
            DownloadService(tmp_path / "downloads", tmp_path / "temp", **kwargs)

    def test_thumbnail_dimensions_are_versioned_and_original_is_unchanged(self, tmp_path: Path) -> None:
        original = tmp_path / "original.png"
        Image.new("RGB", (600, 300), (80, 100, 120)).save(original)
        before = compute_sha256(original)
        thumb_dir = tmp_path / "cache" / "thumbnails"
        thumbnail = thumbnail_cache_path(thumb_dir, before, (256, 128), 80)
        assert create_thumbnail(original, thumbnail, (256, 128), 80)
        with Image.open(thumbnail) as image:
            assert image.size == (256, 128)
        assert compute_sha256(original) == before
        assert thumbnail_cache_path(thumb_dir, before, (400, 225), 85) != thumbnail

    def test_thumbnail_cache_budget_only_removes_cache_entries(self, tmp_path: Path) -> None:
        cache = tmp_path / "cache"
        cache.mkdir()
        for name in ("one.jpg", "two.jpg"):
            (cache / name).write_bytes(b"x" * 650_000)
        assert enforce_thumbnail_cache_limit(cache, 1) == 1
        assert sum(path.stat().st_size for path in cache.glob("*.jpg")) <= 1024 * 1024


class TestAttributionAndLogging:
    def test_attribution_csv_unicode_formula_safety_incomplete_and_no_overwrite(self, tmp_path: Path) -> None:
        destination = tmp_path / "attribution.csv"
        wallpaper = Wallpaper(
            filename="山.jpg", path="C:/library/山.jpg", title="=HYPERLINK(\"https://bad\")",
            source="wikimedia", author="Zoë", source_url="https://commons.wikimedia.org/example",
            license="CC BY-SA", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            width=1920, height=1080,
        )
        report = export_attributions([wallpaper], destination)
        assert report.rows_exported == 1
        assert report.rows_with_incomplete_attribution == 0
        with destination.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert rows[0]["creator"] == "Zoë"
        assert rows[0]["title"].startswith("'=")
        with pytest.raises(FileExistsError):
            export_attributions([wallpaper], destination)
        assert destination.exists()

    def test_attribution_quotes_multiline_metadata_and_empty_library(
        self, tmp_path: Path
    ) -> None:
        destination = tmp_path / "quoted.csv"
        title = 'Mountains, "above" the valley\nsecond line'
        export_attributions(
            [Wallpaper(title=title, source_url='https://example.invalid/a,b?title="mountain"')],
            destination,
        )
        with destination.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 1
        assert rows[0]["title"] == title
        assert rows[0]["source_url"] == 'https://example.invalid/a,b?title="mountain"'

        empty_report = export_attributions([], tmp_path / "empty.csv")
        assert empty_report.rows_exported == 0
        assert empty_report.rows_with_incomplete_attribution == 0

    def test_attribution_write_failure_leaves_no_partial_export(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.attribution_export_service as export_module

        destination = tmp_path / "write-failure.csv"

        def fail_link(_source, _target):
            raise OSError("simulated disk failure")

        monkeypatch.setattr(export_module.os, "link", fail_link)
        with pytest.raises(OSError, match="simulated disk failure"):
            export_attributions([Wallpaper(title="Example")], destination)
        assert not destination.exists()
        assert not list(tmp_path.glob(".attribution-*.tmp"))

    def test_local_import_is_not_marked_missing_remote_attribution(self, tmp_path: Path) -> None:
        report = export_attributions([Wallpaper(source="local_import", filename="local.jpg")], tmp_path / "local.csv")
        assert report.rows_with_incomplete_attribution == 0

    def test_logging_reconfiguration_has_no_duplicate_handlers_and_degrades_safely(self, tmp_path: Path) -> None:
        assert setup_logging(tmp_path / "Logs", level_name="WARNING", max_size_mb=2, backup_count=4)
        setup_logging(tmp_path / "Logs", level_name="ERROR", max_size_mb=3, backup_count=2)
        app_handlers = [handler for handler in logging.getLogger().handlers if getattr(handler, "_sandy_app_handler", False)]
        assert len(app_handlers) == 2
        assert logging.getLogger().level == logging.ERROR
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("x", encoding="utf-8")
        assert not setup_logging(blocker / "Logs", file_enabled=True)


def test_integrated_settings_save_and_rotation_tab(qapp, phase10_db: Database, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    library_root = tmp_path / "library"
    library_root.mkdir()
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    config = Config(config_dir)
    scheduler = RotationScheduler(database_path=phase10_db.path)
    view = SettingsView(config, phase10_db, scheduler)
    try:
        assert view.tabs.count() == 5
        view._widgets["library_path"].setText(str(library_root))
        view._widgets["download_folder"].setText(str(downloads))
        view._widgets["recursive_import"].setChecked(True)
        view._widgets["phash_threshold"].setValue(22)
        view._widgets["thumbnail_width"].setValue(512)
        view._widgets["wallpaper_style"].setCurrentText("Fit")
        view._save()
        assert config.library_path == library_root
        assert config.get("recursive_import") is True
        assert config.get("phash_threshold") == 22
        assert config.get("thumbnail_width") == 512
        assert config.get("wallpaper_style") == "Fit"
        assert not view.save_button.isEnabled()
    finally:
        scheduler.shutdown()
        view.close()


def test_settings_navigation_cancel_validation_and_reset_preserves_rotation(
    qapp, phase10_db: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    default_library = config_dir / "Library"
    default_library.mkdir()
    config = Config(config_dir)
    config.set_rotation_preferences(RotationPreferences(enabled=True, interval_minutes=30))
    config.save()
    scheduler = RotationScheduler(database_path=phase10_db.path)
    view = SettingsView(config, phase10_db, scheduler)
    try:
        for index in range(view.tabs.count()):
            view.tabs.setCurrentIndex(index)
            assert view.tabs.currentIndex() == index

        recursive = view._widgets["recursive_import"]
        assert recursive.isChecked() is False
        recursive.setChecked(True)
        assert view.status.text() == "Unsaved changes"
        assert view.save_button.isEnabled()
        view.cancel_button.click()
        assert recursive.isChecked() is False
        assert not view.save_button.isEnabled()

        original_library = config.library_path
        view._widgets["library_path"].setText(str(tmp_path / "missing-library"))
        view._save()
        assert config.library_path == original_library
        assert "must be an existing folder" in view.status.text()

        rotation = view.tabs.widget(4)

        def fail_save(_values):
            raise OSError("simulated read-only settings")

        with monkeypatch.context() as patcher:
            patcher.setattr(config, "apply_settings", fail_save)
            rotation._stop_rotation()
            assert rotation._enabled.isChecked()
            assert config.rotation_preferences.enabled is True

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
        )
        view._reset_defaults()
        assert config.library_path == default_library
        assert config.get("recursive_import") is False
        assert config.rotation_preferences.enabled is True
        assert config.rotation_preferences.interval_minutes == 30
    finally:
        scheduler.shutdown()
        view.close()


def test_background_thumbnail_worker_rebuild_and_cancel(
    phase10_db: Database, tmp_path: Path
) -> None:
    from app.ui.settings_view import _MaintenanceWorker

    config = Config(tmp_path / "worker-config")
    image_path = tmp_path / "worker-input.jpg"
    Image.new("RGB", (600, 300), (120, 90, 70)).save(image_path)
    digest = compute_sha256(image_path)
    WallpaperRepository(phase10_db).add(Wallpaper(
        filename=image_path.name,
        path=str(image_path),
        sha256=digest,
        width=600,
        height=300,
    ))

    completed: list[str] = []
    worker = _MaintenanceWorker("thumbnails", config, phase10_db.path)
    worker.completed.connect(completed.append)
    worker.run()
    target = thumbnail_cache_path(config.cache_dir / "thumbnails", digest, (400, 225), 85)
    assert target.is_file()
    assert completed and "1 created" in completed[0]

    integrity: list[str] = []
    integrity_worker = _MaintenanceWorker("integrity", config, phase10_db.path)
    integrity_worker.completed.connect(integrity.append)
    integrity_worker.run()
    assert integrity and "1 records, 0 missing files, 0 missing thumbnails" in integrity[0]

    cancelled: list[str] = []
    cancel_worker = _MaintenanceWorker("thumbnails", config, phase10_db.path)
    cancel_worker.completed.connect(cancelled.append)
    cancel_worker.cancel()
    cancel_worker.run()
    assert cancelled and "cancelled" in cancelled[0]
