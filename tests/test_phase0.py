"""
Sandy Wallpaper Studio — Phase 0 Tests
=========================================
Tests for configuration, constants, logging, and directory setup.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pytest

from app.config import Config
from app.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_CATEGORIES,
    DEFAULT_SUBDIRS,
    RESOLUTION_CLASSES,
    SUPPORTED_FORMATS,
    WALLPAPER_STYLES,
)
from app.utils.logging_config import setup_logging


# ============================================================
# Constants Tests
# ============================================================
class TestConstants:
    """Verify application constants are properly defined."""

    def test_app_identity(self) -> None:
        assert APP_NAME == "Sandy Wallpaper Studio"
        assert APP_VERSION == "1.0.0"

    def test_resolution_classes_ordered(self) -> None:
        """8K > 5K > 4K must be defined and have correct minimums."""
        assert RESOLUTION_CLASSES["8K"]["min_width"] == 7680
        assert RESOLUTION_CLASSES["5K"]["min_width"] == 5120
        assert RESOLUTION_CLASSES["4K"]["min_width"] == 3840

    def test_supported_formats(self) -> None:
        assert ".jpg" in SUPPORTED_FORMATS
        assert ".jpeg" in SUPPORTED_FORMATS
        assert ".png" in SUPPORTED_FORMATS
        assert ".webp" in SUPPORTED_FORMATS

    def test_wallpaper_styles(self) -> None:
        for style in ("Center", "Fill", "Fit", "Stretch", "Tile"):
            assert style in WALLPAPER_STYLES

    def test_default_categories_nonempty(self) -> None:
        assert len(DEFAULT_CATEGORIES) >= 40  # Plan specifies 45+ categories

    def test_default_categories_unique(self) -> None:
        assert len(DEFAULT_CATEGORIES) == len(set(DEFAULT_CATEGORIES))

    def test_default_subdirs(self) -> None:
        expected = {"Library", "Metadata", "Cache", "Temp", "Logs", "Exports", "Duplicates"}
        assert expected == set(DEFAULT_SUBDIRS)


# ============================================================
# Config Tests
# ============================================================
class TestConfig:
    """Verify the Config manager loads, saves, and merges correctly."""

    def test_default_settings(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        assert config.get("theme") == "dark"
        assert config.get("rotation_enabled") is False
        assert config.get("analytics_enabled") is False

    def test_save_and_load(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        config.set("theme", "light")
        config.save()

        # Load into a fresh Config
        config2 = Config(config_dir=tmp_path)
        config2.load()
        assert config2.get("theme") == "light"

    def test_unknown_key_ignored_on_load(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"theme": "dark", "FAKE_KEY": 42}), encoding="utf-8")

        config = Config(config_dir=tmp_path)
        config.load()
        assert config.get("FAKE_KEY") is None  # Unknown keys are dropped

    def test_unknown_key_rejected_on_set(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        config.set("FAKE_KEY", 42)
        assert config.get("FAKE_KEY") is None

    def test_malformed_json_uses_defaults(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("NOT JSON!", encoding="utf-8")

        config = Config(config_dir=tmp_path)
        config.load()
        assert config.get("theme") == "dark"  # Falls back to default

    def test_reset(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        config.set("theme", "light")
        config.set("rotation_enabled", True)
        config.reset()
        assert config.get("theme") == "dark"
        assert config.get("rotation_enabled") is False

    def test_property_paths(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        assert config.config_dir == tmp_path
        assert config.database_path == tmp_path / "wallpapers.db"
        assert config.cache_dir == tmp_path / "Cache"
        assert config.logs_dir == tmp_path / "Logs"
        assert config.exports_dir == tmp_path / "Exports"
        assert config.duplicates_dir == tmp_path / "Duplicates"
        assert config.temp_dir == tmp_path / "Temp"

    def test_library_path_default(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        assert config.library_path == tmp_path / "Library"

    def test_all_settings_returns_copy(self, tmp_path: Path) -> None:
        config = Config(config_dir=tmp_path)
        s1 = config.all_settings
        s1["theme"] = "HACKED"
        assert config.get("theme") == "dark"  # Original unchanged


# ============================================================
# Logging Tests
# ============================================================
class TestLogging:
    """Verify logging setup creates the log file and outputs correctly."""

    def test_log_file_created(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "Logs"
        setup_logging(logs_dir, debug=False)

        log_file = logs_dir / "app.log"
        assert logs_dir.exists()
        # Write a log message to ensure the file gets created
        logging.getLogger("test").info("Test message")
        assert log_file.exists()

    def test_debug_level(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "Logs"
        setup_logging(logs_dir, debug=True)
        root = logging.getLogger()
        assert root.level == logging.DEBUG


# ============================================================
# Directory Structure Tests
# ============================================================
class TestDirectoryStructure:
    """Verify that _ensure_directory_structure creates all required dirs."""

    def test_ensure_directories(self, tmp_path: Path) -> None:
        from app.main import _ensure_directory_structure

        config = Config(config_dir=tmp_path)
        _ensure_directory_structure(config)

        for subdir in DEFAULT_SUBDIRS:
            assert (tmp_path / subdir).is_dir(), f"Missing directory: {subdir}"
