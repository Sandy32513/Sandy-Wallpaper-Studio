"""
Sandy Wallpaper Studio - Logging Configuration
=================================================
Sets up rotating file and console logging.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.constants import LOG_BACKUP_COUNT, LOG_FILENAME, LOG_MAX_BYTES


def setup_logging(logs_dir: Path, debug: bool = False) -> None:
    """Configure application-wide logging.

    Args:
        logs_dir: Directory where log files will be written.
        debug: If True, set log level to DEBUG; otherwise INFO.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / LOG_FILENAME

    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to prevent duplicates on reload
    root_logger.handlers.clear()

    # -- File handler (rotating) --
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    root_logger.addHandler(file_handler)

    # -- Console handler (stderr) --
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING if not debug else logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info(
        "Logging initialized — level=%s, file=%s", logging.getLevelName(level), log_file
    )
