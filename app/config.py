"""
Sandy Wallpaper Studio - Configuration Manager
=================================================
Handles loading, saving, and validating application settings.
Configuration is stored as a JSON file in the library root.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.constants import (
    CACHE_MAX_SIZE_MB,
    DEFAULT_LIBRARY_DIR_NAME,
    DEFAULT_MAX_DOWNLOAD_SIZE_MB,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
    DEFAULT_PHASH_THRESHOLD,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    MIN_ACCEPTED_HEIGHT,
    MIN_ACCEPTED_WIDTH,
)

logger = logging.getLogger(__name__)

ROTATION_MIN_INTERVAL_MINUTES = 1
ROTATION_MAX_INTERVAL_MINUTES = 10_080
ROTATION_MAX_DIMENSION = 32_768


@dataclass(frozen=True)
class RotationPreferences:
    """Validated, persistent preferences for in-process wallpaper rotation."""

    enabled: bool = False
    interval_minutes: int = 60
    random_selection: bool = True
    categories: tuple[str, ...] = ()
    min_width: int = 0
    min_height: int = 0

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("Rotation enabled must be true or false.")
        if type(self.random_selection) is not bool:
            raise ValueError("Random selection must be true or false.")
        if type(self.interval_minutes) is not int or not (
            ROTATION_MIN_INTERVAL_MINUTES
            <= self.interval_minutes
            <= ROTATION_MAX_INTERVAL_MINUTES
        ):
            raise ValueError("Rotation interval must be between 1 and 10080 minutes.")
        if any(
            type(dimension) is not int or dimension < 0 or dimension > ROTATION_MAX_DIMENSION
            for dimension in (self.min_width, self.min_height)
        ):
            raise ValueError("Minimum dimensions must be between 0 and 32768 pixels.")
        if not isinstance(self.categories, tuple) or any(
            not isinstance(category, str) or not category.strip()
            for category in self.categories
        ):
            raise ValueError("Rotation categories must be non-empty category names.")

# ============================================================
# Default Settings
# ============================================================
_DEFAULT_SETTINGS: dict[str, Any] = {
    "config_schema_version": 2,
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
    "max_download_size_mb": DEFAULT_MAX_DOWNLOAD_SIZE_MB,
    "max_retries": DEFAULT_MAX_RETRIES,
    "retry_backoff_factor": DEFAULT_RETRY_BACKOFF_FACTOR,

    # --- Library ---
    "auto_organize_by_category": True,
    "recursive_import": False,
    # --- Wallpaper ---
    "wallpaper_style": "Fill",

    # --- Rotation ---
    "rotation_enabled": False,
    "rotation_interval": "1 hour",
    "rotation_mode": "Random",
    "rotation_interval_minutes": 60,
    "rotation_random": True,
    "rotation_categories": [],
    "rotation_min_width": 0,
    "rotation_min_height": 0,

    # --- Sources ---
    "enabled_sources": ["wikimedia"],
    "source_result_limit": 20,

    # --- Performance ---
    "thumbnail_cache_size_mb": CACHE_MAX_SIZE_MB,
    "lazy_load_thumbnails": True,
    "thumbnail_enabled": True,
    "thumbnail_width": 400,
    "thumbnail_height": 225,
    "thumbnail_quality": 85,

    # --- Privacy ---
    "analytics_enabled": False,  # Always False; we never collect data

    # --- Duplicate Detection ---
    "phash_threshold": DEFAULT_PHASH_THRESHOLD,
    "log_level": "INFO",
    "file_logging_enabled": True,
    "log_max_size_mb": 5,
    "log_backup_count": 3,
}

_BOOL_KEYS = {
    "start_with_windows", "check_updates", "auto_organize_by_category",
    "recursive_import", "rotation_enabled", "rotation_random",
    "lazy_load_thumbnails", "thumbnail_enabled", "analytics_enabled",
    "file_logging_enabled",
}
_INT_RANGES: dict[str, tuple[int, int]] = {
    "max_simultaneous_downloads": (1, 8), "timeout_seconds": (1, 300),
    "max_download_size_mb": (1, 2048), "max_retries": (1, 10),
    "min_resolution_width": (0, 32768), "min_resolution_height": (0, 32768),
    "rotation_interval_minutes": (ROTATION_MIN_INTERVAL_MINUTES, ROTATION_MAX_INTERVAL_MINUTES),
    "rotation_min_width": (0, ROTATION_MAX_DIMENSION),
    "rotation_min_height": (0, ROTATION_MAX_DIMENSION),
    "source_result_limit": (1, 50), "thumbnail_width": (64, 1024),
    "thumbnail_height": (64, 1024), "thumbnail_quality": (50, 95),
    "thumbnail_cache_size_mb": (50, 2048), "phash_threshold": (0, 64),
    "log_max_size_mb": (1, 100), "log_backup_count": (1, 10),
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
            with open(self._config_path, encoding="utf-8") as f:
                user_settings = json.load(f)
            if not isinstance(user_settings, dict):
                logger.warning("Config file is not a JSON object — using defaults.")
                return
            if "rotation_interval_minutes" not in user_settings:
                legacy_interval = user_settings.get("rotation_interval")
                parsed_interval = self._parse_legacy_rotation_interval(legacy_interval)
                if parsed_interval is not None:
                    self._settings["rotation_interval_minutes"] = parsed_interval
            # Validate keys independently: one damaged value must not hide valid settings.
            for key, value in user_settings.items():
                if key not in _DEFAULT_SETTINGS:
                    logger.warning("Unknown config key ignored: %s", key)
                    continue
                try:
                    self._settings[key] = self._validate_value(key, value)
                except ValueError as exc:
                    logger.warning("Invalid config setting %s ignored: %s", key, exc)
            logger.info("Configuration loaded from %s", self._config_path)
        except json.JSONDecodeError as exc:
            logger.error("Malformed config file: %s — using defaults.", exc)
        except OSError as exc:
            logger.error("Could not read config file: %s — using defaults.", exc)

    def save(self) -> None:
        """Atomically persist current settings. Raises OSError on disk failures."""
        temporary_path: Path | None = None
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self._config_dir,
                prefix=".settings-", suffix=".tmp", delete=False,
            ) as f:
                temporary_path = Path(f.name)
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, self._config_path)
            logger.info("Configuration saved to %s", self._config_path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            logger.error("Could not save configuration.")
            raise OSError("Could not save configuration.") from exc

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting by key."""
        return self._settings.get(key, default)

    def snapshot(self) -> Config:
        """Create an in-memory copy for a long-running operation."""
        copy = Config(self._config_dir)
        copy._settings = dict(self._settings)
        return copy

    def set(self, key: str, value: Any) -> None:
        """Update a setting. The key must be a known setting."""
        if key not in _DEFAULT_SETTINGS:
            logger.warning("Attempt to set unknown config key: %s", key)
            return
        self._settings[key] = self._validate_value(key, value)

    def apply_settings(self, values: dict[str, Any]) -> None:
        """Validate, persist and then apply a set of preferences atomically."""
        candidate = dict(self._settings)
        for key, value in values.items():
            if key not in _DEFAULT_SETTINGS:
                raise KeyError(f"Unknown configuration setting: {key}")
            candidate[key] = self._validate_value(key, value)
        # Use a temporary candidate so failed persistence never changes live settings.
        current = self._settings
        self._settings = candidate
        try:
            self.save()
        except OSError:
            self._settings = current
            raise

    @staticmethod
    def _validate_value(key: str, value: Any) -> Any:
        if key in _BOOL_KEYS:
            if type(value) is not bool:
                raise ValueError("must be true or false")
            return value
        if key in _INT_RANGES:
            minimum, maximum = _INT_RANGES[key]
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"must be an integer from {minimum} to {maximum}")
            return value
        if key == "retry_backoff_factor":
            if type(value) not in (int, float) or not math.isfinite(value) or not 1 <= value <= 10:
                raise ValueError("must be a finite number from 1 to 10")
            return float(value)
        if key in {"library_path", "download_folder"}:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("must be a non-empty path")
            return str(Path(value).expanduser())
        if key == "enabled_sources":
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError("must be a list of source names")
            if any(item != "wikimedia" for item in value):
                raise ValueError("only the Wikimedia source is currently supported")
            return list(dict.fromkeys(value))
        if key == "rotation_categories":
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError("must be a list of category names")
            return list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if key == "wallpaper_style":
            if not isinstance(value, str) or value not in {"Center", "Tile", "Stretch", "Fit", "Fill", "Span"}:
                raise ValueError("unsupported wallpaper style")
            return value
        if key == "log_level":
            if not isinstance(value, str) or value.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
                raise ValueError("must be DEBUG, INFO, WARNING or ERROR")
            return value.upper()
        if key in {"theme", "preferred_aspect_ratio", "rotation_interval", "rotation_mode"}:
            if not isinstance(value, str):
                raise ValueError("must be text")
            return value
        if key == "config_schema_version":
            if type(value) is not int or not 1 <= value <= 2:
                raise ValueError("unsupported configuration schema version")
            return 2
        return value

    @staticmethod
    def _parse_legacy_rotation_interval(value: Any) -> int | None:
        """Read older human-readable rotation intervals when upgrading settings."""
        if not isinstance(value, str):
            return None
        match = re.fullmatch(r"\s*(\d+)\s*(minute|minutes|min|hour|hours|day|days)\s*", value, re.I)
        if not match:
            return None
        amount = int(match.group(1))
        unit = match.group(2).lower()
        multiplier = 1 if unit.startswith("min") else (60 if unit.startswith("hour") else 1440)
        minutes = amount * multiplier
        if not ROTATION_MIN_INTERVAL_MINUTES <= minutes <= ROTATION_MAX_INTERVAL_MINUTES:
            return None
        return minutes

    @property
    def rotation_preferences(self) -> RotationPreferences:
        """Return validated rotation preferences, falling back safely on bad values."""
        interval = self._settings.get("rotation_interval_minutes", 60)
        if type(interval) is not int or not (
            ROTATION_MIN_INTERVAL_MINUTES <= interval <= ROTATION_MAX_INTERVAL_MINUTES
        ):
            interval = 60
            logger.warning("Invalid rotation interval in settings; using 60 minutes.")

        categories = self._settings.get("rotation_categories", [])
        if not isinstance(categories, list):
            categories = []
            logger.warning("Invalid rotation categories in settings; using all categories.")
        safe_categories = tuple(
            dict.fromkeys(
                category.strip()
                for category in categories
                if isinstance(category, str) and category.strip()
            )
        )

        dimensions: list[int] = []
        for key in ("rotation_min_width", "rotation_min_height"):
            value = self._settings.get(key, 0)
            if type(value) is not int or not 0 <= value <= ROTATION_MAX_DIMENSION:
                value = 0
                logger.warning("Invalid %s in settings; disabling that dimension filter.", key)
            dimensions.append(value)

        enabled = self._settings.get("rotation_enabled", False)
        random_selection = self._settings.get("rotation_random", True)
        return RotationPreferences(
            enabled=enabled if type(enabled) is bool else False,
            interval_minutes=interval,
            random_selection=random_selection if type(random_selection) is bool else True,
            categories=safe_categories,
            min_width=dimensions[0],
            min_height=dimensions[1],
        )

    def set_rotation_preferences(self, preferences: RotationPreferences) -> None:
        """Replace the persisted automatic rotation preferences."""
        self._settings.update(
            {
                "rotation_enabled": preferences.enabled,
                "rotation_interval_minutes": preferences.interval_minutes,
                "rotation_random": preferences.random_selection,
                "rotation_categories": list(preferences.categories),
                "rotation_min_width": preferences.min_width,
                "rotation_min_height": preferences.min_height,
            }
        )

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
