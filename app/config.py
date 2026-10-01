"""
Sandy Wallpaper Studio - Configuration Manager
=================================================
Handles loading, saving, and validating application settings.
Configuration is stored as a JSON file in the library root.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.constants import (
    APP_NAME,
    CACHE_MAX_SIZE_MB,
    DEFAULT_LIBRARY_DIR_NAME,
    DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
    DEFAULT_PHASH_THRESHOLD,
    DEFAULT_TIMEOUT_SECONDS,
    MIN_ACCEPTED_HEIGHT,
    MIN_ACCEPTED_WIDTH,
)

logger = logging.getLogger(__name__)

# ============================================================
# Default Settings
# ============================================================
_DEFAULT_SETTINGS: dict[str, Any] = {
    # --- General ---
    "library_path": "",  # Set dynamically at first launch
    "theme": "dark",
    "start_with_windows": False,
    "check_updates": False,

    # --- Downloads ---
    "download_folder": "",  # Set dynamically
    "min_resolution_width": MIN_ACCEPTED_WIDTH,
    "min_resolution_height": MIN_ACCEPTED_HEIGHT,
    "preferred_aspect_ratio": "any",
    "max_simultaneous_downloads": DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,

    # --- Library ---
    "auto_organize_by_category": True,

    # --- Wallpaper ---
    "wallpaper_style": "Fill",

    # --- Rotation ---
    "rotation_enabled": False,
    "rotation_interval": "1 hour",
    "rotation_mode": "Random",

    # --- Sources ---
    "enabled_sources": ["wikimedia"],

    # --- Performance ---
    "thumbnail_cache_size_mb": CACHE_MAX_SIZE_MB,
    "lazy_load_thumbnails": True,

    # --- Privacy ---
    "analytics_enabled": False,  # Always False; we never collect data

    # --- Duplicate Detection ---
    "phash_threshold": DEFAULT_PHASH_THRESHOLD,
}

CONFIG_FILENAME = "settings.json"


class Config:
    """Application configuration manager.

    Loads settings from a JSON file and provides typed access.
    Falls back to defaults for any missing keys.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        if config_dir is None:
            pictures = Path.home() / "Pictures"
            config_dir = pictures / DEFAULT_LIBRARY_DIR_NAME
        self._config_dir = config_dir
        self._config_path = config_dir / CONFIG_FILENAME
        self._settings: dict[str, Any] = dict(_DEFAULT_SETTINGS)

        # Resolve dynamic defaults
        if not self._settings["library_path"]:
            self._settings["library_path"] = str(config_dir / "Library")
        if not self._settings["download_folder"]:
            self._settings["download_folder"] = str(config_dir / "Library")

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def load(self) -> None:
        """Load configuration from disk, merging with defaults."""
        if not self._config_path.exists():
            logger.info("No config file found at %s — using defaults.", self._config_path)
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            if not isinstance(user_settings, dict):
                logger.warning("Config file is not a JSON object — using defaults.")
                return
            # Merge: user overrides defaults
            for key, value in user_settings.items():
                if key in _DEFAULT_SETTINGS:
                    self._settings[key] = value
                else:
                    logger.warning("Unknown config key ignored: %s", key)
            logger.info("Configuration loaded from %s", self._config_path)
        except json.JSONDecodeError as exc:
            logger.error("Malformed config file: %s — using defaults.", exc)
        except OSError as exc:
            logger.error("Could not read config file: %s — using defaults.", exc)

    def save(self) -> None:
        """Persist current settings to disk."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved to %s", self._config_path)
        except OSError as exc:
            logger.error("Could not save config: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting by key."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Update a setting. The key must be a known setting."""
        if key not in _DEFAULT_SETTINGS:
            logger.warning("Attempt to set unknown config key: %s", key)
            return
        self._settings[key] = value

    def reset(self) -> None:
        """Reset all settings to defaults."""
        self._settings = dict(_DEFAULT_SETTINGS)
        # Re-resolve dynamic defaults
        if not self._settings["library_path"]:
            self._settings["library_path"] = str(self._config_dir / "Library")
        if not self._settings["download_folder"]:
            self._settings["download_folder"] = str(self._config_dir / "Library")
        logger.info("Configuration reset to defaults.")

    @property
    def library_path(self) -> Path:
        return Path(self._settings["library_path"])

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def database_path(self) -> Path:
        from app.constants import DATABASE_FILENAME
        return self._config_dir / DATABASE_FILENAME

    @property
    def cache_dir(self) -> Path:
        return self._config_dir / "Cache"

    @property
    def temp_dir(self) -> Path:
        return self._config_dir / "Temp"

    @property
    def logs_dir(self) -> Path:
        return self._config_dir / "Logs"

    @property
    def exports_dir(self) -> Path:
        return self._config_dir / "Exports"

    @property
    def duplicates_dir(self) -> Path:
        return self._config_dir / "Duplicates"

    @property
    def all_settings(self) -> dict[str, Any]:
        """Return a copy of all settings."""
        return dict(self._settings)

    def __repr__(self) -> str:
        return f"Config(config_dir={self._config_dir!r})"
