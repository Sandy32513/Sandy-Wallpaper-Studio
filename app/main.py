"""Sandy Wallpaper Studio - Main Entry Point
===============================================
Initializes configuration, logging, directory structure,
and launches the application.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.config import Config
from app.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_LIBRARY_DIR_NAME,
    DEFAULT_SUBDIRS,
)
from app.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def _report_command_message(message: str, *, error: bool = False) -> None:
    """Report a CLI result in a console or a windowed Windows build."""
    if sys.stdout is not None:
        stream = sys.stderr if error and sys.stderr is not None else sys.stdout
        print(message, file=stream)
    elif sys.platform == "win32":
        import ctypes

        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, flags)  # type: ignore[attr-defined]


class _VersionAction(argparse.Action):
    """Show the version in the console or a native dialog for windowed builds."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        message = f"{APP_NAME} {APP_VERSION}"
        _report_command_message(message)
        parser.exit()


def _ensure_directory_structure(config: Config) -> None:
    """Create the library directory tree if it doesn't exist."""
    base = config.config_dir
    base.mkdir(parents=True, exist_ok=True)

    for subdir_name in DEFAULT_SUBDIRS:
        subdir = base / subdir_name
        subdir.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory: %s", subdir)

    logger.info("Library directory structure verified at %s", base)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="sandy-wallpaper-studio",
        description=f"{APP_NAME} {APP_VERSION} — Professional Wallpaper Manager",
    )
    parser.add_argument(
        "--version",
        action=_VersionAction,
        nargs=0,
        help="Show the application version.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging.",
    )
    parser.add_argument(
        "--library",
        type=str,
        default=None,
        help="Override the library root directory.",
    )
    parser.add_argument("--validate-runtime", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prepare-runtime-check", action="store_true", help=argparse.SUPPRESS)

    # --- Future CLI commands (Phase 33) ---
    parser.add_argument("--download", action="store_true", help="(Planned) Download wallpapers.")
    parser.add_argument("--category", type=str, help="(Planned) Filter by category.")
    parser.add_argument("--resolution", type=str, help="(Planned) Filter by resolution class.")
    parser.add_argument("--set-random", action="store_true", help="(Planned) Set a random wallpaper.")
    parser.add_argument("--set", type=str, dest="set_wallpaper", help="(Planned) Set wallpaper by path.")
    parser.add_argument("--cleanup-duplicates", action="store_true", help="(Planned) Interactive duplicate cleanup.")
    parser.add_argument("--stats", action="store_true", help="(Planned) Show library statistics.")

    return parser.parse_args()


def _prepare_packaged_runtime_check(config: Config, db: Any) -> int:
    """Import a generated supported image and persist a test setting in a frozen build."""
    from PIL import Image

    from app.services.import_service import FileStatus, ImportService

    try:
        config.temp_dir.mkdir(parents=True, exist_ok=True)
        image_folder = config.temp_dir / "sws-packaged-import-input"
        image_folder.mkdir(parents=True, exist_ok=True)
        image_path = image_folder / "sws-runtime-import.png"
        with Image.new("RGB", (256, 192), (48, 96, 144)) as image:
            image.save(image_path, format="PNG")

        report = ImportService(db, cache_dir=config.cache_dir, config=config).import_folder(image_folder)
        if report.total_discovered != 1 or report.total_imported != 1:
            raise RuntimeError(f"Supported image import failed: {report.summary_dict()}")
        if report.file_results[0].status not in {FileStatus.IMPORTED, FileStatus.NEAR_DUPLICATE_IMPORTED}:
            raise RuntimeError(f"Supported image import returned {report.file_results[0].status.value}.")

        config.apply_settings({"theme": "light"})
        db.close()
        _report_command_message(
            f"{APP_NAME} {APP_VERSION}\n"
            "Prepare check passed: supported image import and persisted setting."
        )
        return 0
    except Exception as exc:
        logger.exception("Packaged runtime preparation failed.")
        try:
            db.close()
        except Exception:
            logger.exception("Could not close the database after runtime preparation failure.")
        _report_command_message(
            f"{APP_NAME} prepare check failed: {type(exc).__name__}: {exc}",
            error=True,
        )
        return 1


def _validate_packaged_runtime(config: Config, db: Any) -> int:
    """Verify imported data and settings persisted across a packaged process restart."""
    from PIL import Image

    from app.database.wallpaper_repository import WallpaperRepository
    from app.services.metadata_service import MetadataService
    from app.utils.hashing import compute_phash, compute_sha256
    from app.utils.image_utils import thumbnail_cache_path

    try:
        image_path = config.temp_dir / "sws-packaged-import-input" / "sws-runtime-import.png"
        wallpaper = WallpaperRepository(db).get_by_path(str(image_path.resolve()))
        if wallpaper is None or not image_path.is_file():
            raise RuntimeError("Imported image was not persisted across process restart.")

        metadata = MetadataService().extract(image_path)
        sha256 = compute_sha256(image_path)
        phash = compute_phash(image_path)
        if (not metadata.sha256 or len(sha256) != 64 or len(phash) != 16 or
                wallpaper.sha256 != sha256 or wallpaper.phash != phash):
            raise RuntimeError("Imported image metadata, SHA-256, or pHash validation failed.")

        thumbnail_size = (
            config.get("thumbnail_width", 400),
            config.get("thumbnail_height", 225),
        )
        thumbnail = thumbnail_cache_path(
            config.cache_dir / "thumbnails",
            sha256,
            thumbnail_size,
            config.get("thumbnail_quality", 85),
        )
        if not thumbnail.is_file():
            raise RuntimeError("ImportService thumbnail was not persisted.")
        with Image.open(thumbnail) as image:
            image.verify()

        settings_path = config.config_dir / "settings.json"
        persisted_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if (persisted_settings.get("config_schema_version") != 2 or
                persisted_settings.get("theme") != "light" or config.get("theme") != "light"):
            raise RuntimeError("Persisted settings did not survive a fresh process.")
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity validation failed: {integrity}")

        db.close()
        _report_command_message(
            f"{APP_NAME} {APP_VERSION}\n"
            "Runtime check passed after restart: imported image, metadata, SHA-256, "
            "pHash, thumbnail, persisted setting, and SQLite integrity."
        )
        return 0
    except Exception as exc:
        logger.exception("Packaged runtime validation failed.")
        try:
            db.close()
        except Exception:
            logger.exception("Could not close the database after runtime validation failure.")
        _report_command_message(
            f"{APP_NAME} runtime check failed: {type(exc).__name__}: {exc}",
            error=True,
        )
        return 1


def main() -> int:
    """Application entry point."""
    args = _parse_args()

    # Determine library root
    if args.library:
        config_dir = Path(args.library)
    else:
        config_dir = Path.home() / "Pictures" / DEFAULT_LIBRARY_DIR_NAME

    # Initialize configuration
    config = Config(config_dir=config_dir)
    config.load()

    # Set up logging
    setup_logging(
        config.logs_dir,
        debug=args.debug,
        level_name=config.get("log_level", "INFO"),
        file_enabled=config.get("file_logging_enabled", True),
        max_size_mb=config.get("log_max_size_mb", 5),
        backup_count=config.get("log_backup_count", 3),
    )
    logger.info("=" * 60)
    logger.info("%s %s — Starting", APP_NAME, APP_VERSION)
    logger.info("=" * 60)
    logger.info("Library root: %s", config.config_dir)
    logger.info("Database: %s", config.database_path)

    # Ensure directory structure
    _ensure_directory_structure(config)

    # Save config (creates settings.json if first run)
    try:
        config.save()
    except OSError:
        logger.warning("Configuration could not be saved; the application will continue with in-memory defaults.")

    # -------------------------------------------------------
    # Database Initialization (Phase 1)
    # -------------------------------------------------------
    from app.database import CategoryRepository, Database

    db = Database(config.database_path)
    db.connect()

    # Seed default categories on first run
    cat_repo = CategoryRepository(db)
    cat_repo.seed_defaults()

    logger.info("%s initialized successfully.", APP_NAME)

    if getattr(args, "validate_runtime", False):
        return _validate_packaged_runtime(config, db)
    if getattr(args, "prepare_runtime_check", False):
        return _prepare_packaged_runtime_check(config, db)

    # -------------------------------------------------------
    # Phase 6: Launch PySide6 Desktop GUI
    # -------------------------------------------------------
    gui_mode = not getattr(args, "no_gui", False)

    if gui_mode:
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QApplication

            from app.ui.main_window import MainWindow

            app = QApplication.instance() or QApplication(sys.argv)
            app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
            app.setApplicationName(APP_NAME)
            app.setApplicationVersion(APP_VERSION)
            app.setOrganizationName("Sandy")

            window = MainWindow(config=config, db=db)
            window.show()
            exit_code = app.exec()
            logger.info("%s — shutdown.", APP_NAME)
            return exit_code

        except Exception:
            logger.exception("GUI launch failed.")
            if sys.stdout is None:
                db.close()
                return 1
            # Fallback to console report
            gui_mode = False

    from app.database.category_repository import CategoryRepository
    from app.database.wallpaper_repository import WallpaperRepository
    from app.services.wallpaper_service import WindowsWallpaperService

    cat_repo2 = CategoryRepository(db)
    cat_count = cat_repo2.count()
    wp_repo = WallpaperRepository(db)
    wp_count = wp_repo.count()
    wp_svc = WindowsWallpaperService(db=db, wallpaper_repo=wp_repo)
    monitors = wp_svc.detect_monitors()

    print(f"\n  {APP_NAME} {APP_VERSION}")
    print(f"  Library:     {config.config_dir}")
    print(f"  Database:    {config.database_path}")
    print(f"  Categories:  {cat_count}")
    print(f"  Wallpapers:  {wp_count}")
    print(f"  Monitors:    {len(monitors)} detected")
    print("\n  [Phase 6] GUI initialization failed — running in console mode.\n")
    db.close()
    logger.info("%s — shutdown.", APP_NAME)
    return 0



if __name__ == "__main__":
    sys.exit(main())
