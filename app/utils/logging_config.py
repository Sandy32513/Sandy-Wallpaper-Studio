"""Configurable rotating file and console logging."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.constants import LOG_BACKUP_COUNT, LOG_FILENAME, LOG_MAX_BYTES


def setup_logging(
    logs_dir: Path,
    debug: bool = False,
    *,
    level_name: str = "INFO",
    file_enabled: bool = True,
    max_size_mb: int = LOG_MAX_BYTES // (1024 * 1024),
    backup_count: int = LOG_BACKUP_COUNT,
) -> bool:
    """Configure logging without removing handlers installed by other libraries.

    Returns whether file output is active. Logging continues on stderr when a log
    directory is unavailable or the file cannot be opened.
    """
    level = logging.DEBUG if debug else getattr(logging, level_name.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        if getattr(handler, "_sandy_app_handler", False):
            root_logger.removeHandler(handler)
            handler.close()

    if sys.stderr is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler._sandy_app_handler = True  # type: ignore[attr-defined]
        console_handler.setLevel(logging.WARNING if not debug else logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
        root_logger.addHandler(console_handler)

    file_active = False
    if file_enabled:
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                logs_dir / LOG_FILENAME,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler._sandy_app_handler = True  # type: ignore[attr-defined]
            file_handler.setLevel(level)
            file_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
            root_logger.addHandler(file_handler)
            file_active = True
        except OSError:
            root_logger.warning("File logging is unavailable; continuing with console logging.")

    logging.getLogger(__name__).info(
        "Logging initialized: level=%s, file_enabled=%s",
        logging.getLevelName(level), file_active,
    )
    return file_active
