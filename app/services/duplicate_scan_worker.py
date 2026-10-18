"""Qt workers for read-only duplicate scans and cleanup previews."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.database.database import Database
from app.database.wallpaper_repository import WallpaperRepository
from app.services.duplicate_scan_service import (
    CleanupPreview,
    DuplicateScanReport,
    DuplicateScanService,
    build_cleanup_preview,
)


class DuplicateScanWorker(QThread):
    """Load a read-only database snapshot and scan it off the GUI thread."""

    progress = Signal(int, int, str)
    report_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        database_path: Path,
        threshold: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._threshold = threshold
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        database = Database(self._database_path, read_only=True)
        try:
            database.connect()
            database.execute("BEGIN")
            repository = WallpaperRepository(database)
            total = repository.count()
            wallpapers = []
            for offset in range(0, total, 250):
                if self._cancel_event.is_set():
                    database.rollback()
                    self.report_ready.emit(None)
                    return
                wallpapers.extend(repository.get_all(limit=250, offset=offset, order_by="id ASC"))
            database.rollback()
        except Exception as exc:
            self.failed.emit(f"Could not read the wallpaper library ({type(exc).__name__}).")
            return
        finally:
            database.close()

        try:
            report = DuplicateScanService(wallpapers, self._threshold).scan(
                self._cancel_event,
                lambda done, count, _name: self.progress.emit(done, count, "Scanning library files"),
            )
            self.report_ready.emit(report)
        except Exception as exc:
            self.failed.emit(f"Duplicate scan failed ({type(exc).__name__}).")


class CleanupPreviewWorker(QThread):
    """Revalidate a proposed cleanup plan without modifying the library."""

    preview_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        report: DuplicateScanReport,
        removals_by_group: Mapping[str, set[int]],
        keep_by_group: Mapping[str, int],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report = report
        self._removals = {key: set(value) for key, value in removals_by_group.items()}
        self._keeps = dict(keep_by_group)
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        try:
            preview = build_cleanup_preview(
                self._report,
                self._removals,
                self._keeps,
                self._cancel_event,
            )
        except Exception as exc:
            message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            self.failed.emit(message)
        else:
            self.preview_ready.emit(preview)


__all__ = ["CleanupPreview", "CleanupPreviewWorker", "DuplicateScanWorker"]
