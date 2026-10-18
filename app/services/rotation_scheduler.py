"""Qt-based in-process rotation scheduling and worker lifecycle management."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from app.config import RotationPreferences
from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.wallpaper_repository import WallpaperRepository
from app.services.rotation_service import RotationResult, RotationService
from app.services.wallpaper_service import WindowsWallpaperService

logger = logging.getLogger(__name__)


class _RotationWorker(QThread):
    """Perform candidate image checks and desktop application off the GUI thread."""

    completed = Signal(object)

    def __init__(
        self,
        database_path: Path,
        preferences: RotationPreferences,
        style: str,
        cancellation: Event,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._preferences = preferences
        self._style = style
        self._cancellation = cancellation

    def run(self) -> None:
        db = Database(self._database_path)
        try:
            db.connect()
            wallpaper_repository = WallpaperRepository(db)
            history_repository = HistoryRepository(db)
            wallpaper_service = WindowsWallpaperService(
                db=db,
                wallpaper_repo=wallpaper_repository,
                history_repo=history_repository,
            )
            service = RotationService(
                wallpaper_repository=wallpaper_repository,
                wallpaper_service=wallpaper_service,
                history_repository=history_repository,
            )
            result = service.rotate_once(
                self._preferences,
                style=self._style,
                cancellation=self._cancellation,
            )
        except Exception as exc:
            logger.exception("Automatic rotation worker failed")
            result = RotationResult(
                success=False,
                error=type(exc).__name__,
                message=f"Automatic rotation failed: {exc}",
            )
        finally:
            db.close()
        self.completed.emit(result)


class RotationScheduler(QObject):
    """Owns one Qt timer and at most one asynchronous rotation operation."""

    state_changed = Signal(str, str)
    rotation_finished = Signal(object)

    def __init__(
        self,
        database_path: Path,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._clock = clock
        self._wall_clock = wall_clock
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._preferences = RotationPreferences()
        self._style = "Fill"
        self._state = "disabled"
        self._deadline: float | None = None
        self._next_rotation_at: datetime | None = None
        self._remaining_seconds = 0.0
        self._worker: _RotationWorker | None = None
        self._cancellation: Event | None = None
        self._last_result_message = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def timer_active(self) -> bool:
        return self._timer.isActive()

    @property
    def next_rotation_at(self) -> datetime | None:
        return self._next_rotation_at if self._state == "running" else None

    @property
    def remaining_seconds(self) -> float:
        if self._state == "running" and self._deadline is not None:
            return max(0.0, self._deadline - self._clock())
        return self._remaining_seconds

    def start(self, preferences: RotationPreferences, style: str = "Fill") -> None:
        """Enable rotation and schedule its first application after one full interval."""
        self._preferences = preferences
        self._style = style
        if not preferences.enabled:
            self.stop()
            return
        self._state = "running"
        self._last_result_message = ""
        self._schedule(preferences.interval_minutes * 60)
        self._emit_state("Automatic rotation is running.")

    def configure(self, preferences: RotationPreferences, style: str = "Fill") -> None:
        """Apply changed preferences while preserving a paused runtime state."""
        was_paused = self._state == "paused"
        remaining = self.remaining_seconds if self._state == "running" else self._remaining_seconds
        if not preferences.enabled:
            self._preferences = preferences
            self._style = style
            self.stop()
            return
        self._preferences = preferences
        self._style = style
        if was_paused:
            self._remaining_seconds = min(
                remaining, preferences.interval_minutes * 60
            ) or preferences.interval_minutes * 60
            return
        self.start(preferences, style)

    def pause(self) -> None:
        """Pause the schedule and cancel an operation that has not applied yet."""
        if self._state != "running":
            return
        self._remaining_seconds = self.remaining_seconds
        if self._remaining_seconds <= 0:
            self._remaining_seconds = self._preferences.interval_minutes * 60
        self._timer.stop()
        self._deadline = None
        self._next_rotation_at = None
        if self._cancellation is not None:
            self._cancellation.set()
        self._state = "paused"
        self._emit_state("Automatic rotation is paused.")

    def resume(self) -> None:
        """Resume with the remaining delay; an expired delay becomes a full interval."""
        if self._state != "paused" or not self._preferences.enabled:
            return
        delay = self._remaining_seconds
        if delay <= 0:
            delay = self._preferences.interval_minutes * 60
        self._state = "running"
        self._schedule(delay)
        self._emit_state("Automatic rotation resumed.")

    def stop(self) -> None:
        """Cancel the timer and any operation that has not reached desktop application."""
        self._timer.stop()
        self._deadline = None
        self._next_rotation_at = None
        self._remaining_seconds = 0.0
        if self._cancellation is not None:
            self._cancellation.set()
        self._state = "stopped"
        self._emit_state("Automatic rotation is stopped.")

    def shutdown(self) -> None:
        """Stop scheduling and wait for the isolated worker to close its database."""
        self.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()

    def _schedule(self, delay_seconds: float) -> None:
        delay_seconds = max(1.0, delay_seconds)
        self._remaining_seconds = delay_seconds
        self._deadline = self._clock() + delay_seconds
        self._next_rotation_at = self._wall_clock() + timedelta(seconds=delay_seconds)
        self._timer.start(max(1, int(delay_seconds * 1000)))

    def _on_timeout(self) -> None:
        if self._state != "running":
            return
        if self._worker is not None and self._worker.isRunning():
            # Never queue a second application behind a slow local file or desktop API.
            self._schedule(self._preferences.interval_minutes * 60)
            return

        self._deadline = None
        self._next_rotation_at = None
        self._cancellation = Event()
        worker = _RotationWorker(
            database_path=self._database_path,
            preferences=self._preferences,
            style=self._style,
            cancellation=self._cancellation,
            parent=self,
        )
        worker.completed.connect(self._on_rotation_finished)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    @Slot(object)
    def _on_rotation_finished(self, result: RotationResult) -> None:
        if result.error != "CANCELLED":
            if result.success:
                self._last_result_message = f"Last rotation applied wallpaper #{result.wallpaper_id}."
            else:
                self._last_result_message = result.message or "Last rotation attempt failed."
        self.rotation_finished.emit(result)

    @Slot()
    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if not isinstance(worker, _RotationWorker):
            return
        if self._worker is worker:
            self._worker = None
            self._cancellation = None
        worker.deleteLater()
        if self._state == "running":
            self._schedule(self._preferences.interval_minutes * 60)
            message = "Automatic rotation is running."
            if self._last_result_message:
                message = f"{message} {self._last_result_message}"
            self._emit_state(message)

    def _emit_state(self, message: str) -> None:
        self.state_changed.emit(self._state, message)
