"""
Sandy Wallpaper Studio - Configuration Manager
=================================================
Handles loading, saving, and validating application settings.
Configuration is stored as a JSON file in the library root.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.constants import (
    CACHE_MAX_SIZE_MB,
    DEFAULT_LIBRARY_DIR_NAME,
    DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
    DEFAULT_PHASH_THRESHOLD,
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
    "rotation_interval_minutes": 60,
    "rotation_random": True,
    "rotation_categories": [],
    "rotation_min_width": 0,
    "rotation_min_height": 0,

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
