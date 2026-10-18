"""Business logic for selecting and applying automatic wallpaper rotations."""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event

from app.config import RotationPreferences
from app.database.history_repository import HistoryRepository
from app.database.models import Wallpaper, WallpaperHistory
from app.database.wallpaper_repository import WallpaperRepository
from app.services.wallpaper_service import (
    WallpaperApplyResult,
    WindowsWallpaperService,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RotationResult:
    """Result of one automatic rotation attempt."""

    success: bool
    wallpaper_id: int | None = None
    applied_at: str = ""
    error: str = ""
    message: str = ""


class RotationService:
    """Selects a currently valid library image and applies it through the engine."""

    def __init__(
        self,
        wallpaper_repository: WallpaperRepository,
        wallpaper_service: WindowsWallpaperService,
        history_repository: HistoryRepository,
        candidate_order: Callable[[list[Wallpaper]], list[Wallpaper]] | None = None,
    ) -> None:
        self._wallpaper_repository = wallpaper_repository
        self._wallpaper_service = wallpaper_service
        self._history_repository = history_repository
        self._candidate_order = candidate_order or self._random_order

    @staticmethod
    def _random_order(candidates: list[Wallpaper]) -> list[Wallpaper]:
        return random.sample(candidates, k=len(candidates))

    def rotate_once(
        self,
        preferences: RotationPreferences,
        style: str = "Fill",
        cancellation: Event | None = None,
    ) -> RotationResult:
        """Apply one matching wallpaper; no candidate is changed if selection fails."""
        candidates = self._wallpaper_repository.get_rotation_candidates(
            categories=preferences.categories,
            min_width=preferences.min_width,
            min_height=preferences.min_height,
        )
        candidates = [candidate for candidate in candidates if candidate.id is not None]
        if not candidates:
            return RotationResult(
                success=False,
                error="NO_CANDIDATES",
                message="No wallpapers match the selected category and resolution filters.",
            )

        latest = self._history_repository.get_latest()
        previous_id = latest.wallpaper_id if latest else None
        alternatives = [candidate for candidate in candidates if candidate.id != previous_id]

        if preferences.random_selection:
            ordered_alternatives = self._candidate_order(alternatives)
        else:
            ordered_alternatives = self._cycle_order(alternatives, previous_id)

        selected = self._first_valid(ordered_alternatives, cancellation)
        if selected is None and previous_id is not None:
            # Repeat only after every non-repeating candidate was checked and found invalid.
            previous = next((candidate for candidate in candidates if candidate.id == previous_id), None)
            if previous and not self._is_cancelled(cancellation):
                selected = self._first_valid([previous], cancellation)

        if self._is_cancelled(cancellation):
            return RotationResult(
                success=False,
                error="CANCELLED",
                message="Rotation was cancelled before applying a wallpaper.",
            )
        if selected is None:
            return RotationResult(
                success=False,
                error="NO_VALID_CANDIDATES",
                message="No available, supported wallpaper files match the selected filters.",
            )

        try:
            apply_result: WallpaperApplyResult = self._wallpaper_service.set_selected_wallpaper(
                selected,
                style=style,
                source="rotation",
            )
            if not apply_result.success:
                error = apply_result.error or apply_result.message or "Wallpaper application failed."
                self._record_failed_attempt(selected, error)
                return RotationResult(
                    success=False,
                    wallpaper_id=selected.id,
                    error=apply_result.error or "APPLY_FAILED",
                    message=error,
                )
            return RotationResult(
                success=True,
                wallpaper_id=apply_result.wallpaper_id,
                applied_at=apply_result.applied_at,
                message=apply_result.message,
            )
        except Exception as exc:
            logger.exception("Automatic rotation failed for wallpaper id=%s", selected.id)
            self._record_failed_attempt(selected, str(exc))
            return RotationResult(
                success=False,
                wallpaper_id=selected.id,
                error=type(exc).__name__,
                message=f"Could not apply the selected wallpaper: {exc}",
            )

    @staticmethod
    def _cycle_order(candidates: list[Wallpaper], previous_id: int | None) -> list[Wallpaper]:
        """Order IDs after the previous wallpaper first, then wrap to the start."""
        ordered = sorted(candidates, key=lambda candidate: candidate.id or 0)
        if previous_id is None:
            return ordered
        return [
            candidate for candidate in ordered
            if candidate.id is not None and candidate.id > previous_id
        ] + [
            candidate for candidate in ordered
            if candidate.id is not None and candidate.id < previous_id
        ]

    def _first_valid(
        self,
        candidates: list[Wallpaper],
        cancellation: Event | None,
    ) -> Wallpaper | None:
        for candidate in candidates:
            if self._is_cancelled(cancellation):
                return None
            try:
                self._wallpaper_service.validate_image_file(candidate.path)
                return candidate
            except Exception as exc:
                logger.warning(
                    "Skipping ineligible wallpaper id=%s (%s): %s",
                    candidate.id,
                    candidate.filename,
                    exc,
                )
        return None

    @staticmethod
    def _is_cancelled(cancellation: Event | None) -> bool:
        return cancellation is not None and cancellation.is_set()

    def _record_failed_attempt(self, wallpaper: Wallpaper, error: str) -> None:
        if wallpaper.id is None:
            return
        try:
            self._history_repository.add(
                WallpaperHistory(
                    wallpaper_id=wallpaper.id,
                    set_at=datetime.now(UTC).isoformat(),
                    source="rotation",
                    success=False,
                    error_message=error[:500],
                )
            )
        except Exception:
            logger.exception("Could not record failed automatic rotation attempt")
