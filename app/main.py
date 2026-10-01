"""Sandy Wallpaper Studio - Main Entry Point
===============================================
Initializes configuration, logging, directory structure,
and launches the application.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.config import Config
from app.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_LIBRARY_DIR_NAME,
    DEFAULT_SUBDIRS,
)
from app.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


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
        description=f"{APP_NAME} v{APP_VERSION} — Professional Wallpaper Manager",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
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

    # --- Future CLI commands (Phase 33) ---
    parser.add_argument("--download", action="store_true", help="(Planned) Download wallpapers.")
    parser.add_argument("--category", type=str, help="(Planned) Filter by category.")
    parser.add_argument("--resolution", type=str, help="(Planned) Filter by resolution class.")
    parser.add_argument("--set-random", action="store_true", help="(Planned) Set a random wallpaper.")
    parser.add_argument("--set", type=str, dest="set_wallpaper", help="(Planned) Set wallpaper by path.")
    parser.add_argument("--cleanup-duplicates", action="store_true", help="(Planned) Interactive duplicate cleanup.")
    parser.add_argument("--stats", action="store_true", help="(Planned) Show library statistics.")

    return parser.parse_args()


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
    setup_logging(config.logs_dir, debug=args.debug)
    logger.info("=" * 60)
    logger.info("%s v%s — Starting", APP_NAME, APP_VERSION)
    logger.info("=" * 60)
    logger.info("Library root: %s", config.config_dir)
    logger.info("Database: %s", config.database_path)

    # Ensure directory structure
    _ensure_directory_structure(config)

    # Save config (creates settings.json if first run)
    config.save()

    # -------------------------------------------------------
    # Database Initialization (Phase 1)
    # -------------------------------------------------------
    from app.database import Database, CategoryRepository

    db = Database(config.database_path)
    db.connect()

    # Seed default categories on first run
    cat_repo = CategoryRepository(db)
    cat_repo.seed_defaults()

    logger.info("%s initialized successfully.", APP_NAME)

    # -------------------------------------------------------
    # GUI Launch (Phase 6 — currently placeholder)
    # -------------------------------------------------------
    cat_count = cat_repo.count()
    print(f"\n  {APP_NAME} v{APP_VERSION}")
    print(f"  Library: {config.config_dir}")
    print(f"  Database: {config.database_path}")
    print(f"  Categories: {cat_count}")
    print("\n  [Phase 1 Complete] Database initialized.")
    print("  GUI will be available after Phase 6.\n")

    db.close()
    logger.info("%s — shutdown.", APP_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
