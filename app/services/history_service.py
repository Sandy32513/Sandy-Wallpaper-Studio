"""
Sandy Wallpaper Studio — History & Favorites Service
=====================================================
Business logic orchestrating Favorites, Desktop Application History,
Recently Viewed wallpapers, and Recently Downloaded/Imported wallpapers.
"""

from __future__ import annotations

import logging

from app.database.database import Database
from app.database.history_repository import HistoryRepository
from app.database.models import Wallpaper, WallpaperHistory
from app.database.view_repository import ViewRepository
from app.database.wallpaper_repository import WallpaperRepository
from app.services.wallpaper_service import WallpaperApplyResult, WindowsWallpaperService

logger = logging.getLogger(__name__)


class HistoryService:
    """Service providing favorites and history workflows."""

    def __init__(
        self,
        db: Database,
        wallpaper_service: WindowsWallpaperService | None = None,
        wallpaper_repo: WallpaperRepository | None = None,
        history_repo: HistoryRepository | None = None,
        view_repo: ViewRepository | None = None,
    ) -> None:
        self._db = db
        self._wp_repo = wallpaper_repo or WallpaperRepository(db)
        self._history_repo = history_repo or HistoryRepository(db)
        self._view_repo = view_repo or ViewRepository(db)
        self._wp_service = wallpaper_service or WindowsWallpaperService(
            db=db,
            wallpaper_repo=self._wp_repo,
            history_repo=self._history_repo,
        )

    # ==================================================================
    # Favorites Workflows
    # ==================================================================
    def get_favorites(
        self,
        limit: int = 100,
        offset: int = 0,
        category: str | None = None,
        order_by: str = "download_date DESC",
    ) -> list[Wallpaper]:
        """Retrieve favorite wallpapers with optional category filtering and sorting."""
        return self._wp_repo.get_favorites(
            limit=limit,
            offset=offset,
            category=category,
            order_by=order_by,
        )

    def toggle_favorite(self, wallpaper_id: int) -> bool:
        """Toggle favorite status for a wallpaper. Returns the new state."""
        new_state = self._wp_repo.toggle_favorite(wallpaper_id)
        logger.info("Toggled favorite for wallpaper id=%d -> %s", wallpaper_id, new_state)
        return new_state

    def set_favorite(self, wallpaper_id: int, favorite: bool) -> bool:
        """Set favorite status explicitly for a wallpaper."""
        ok = self._wp_repo.set_favorite(wallpaper_id, favorite)
        logger.info(
            "Set favorite for wallpaper id=%d to %s (success=%s)",
            wallpaper_id,
            favorite,
            ok,
        )
        return ok

    def count_favorites(self, category: str | None = None) -> int:
        """Return the total number of favorite wallpapers."""
        return self._wp_repo.count_favorites(category=category)

    def clear_all_favorites(self) -> int:
        """Remove all wallpapers from favorites."""
        cursor = self._db.execute("UPDATE wallpapers SET favorite = 0 WHERE favorite = 1")
        self._db.commit()
        cleared = cursor.rowcount
        logger.info("Cleared all favorites: %d wallpapers updated.", cleared)
        return cleared

    # ==================================================================
    # Recently Applied Workflows (Desktop Wallpaper History)
    # ==================================================================
    def get_recently_applied(
        self,
        limit: int = 50,
        offset: int = 0,
        monitor: str | None = None,
    ) -> list[tuple[WallpaperHistory, Wallpaper | None]]:
        """Fetch history records joined with Wallpaper models, ordered newest first."""
        return self._history_repo.get_recent_with_wallpapers(
            limit=limit,
            offset=offset,
            monitor=monitor,
        )

    def get_recent_rotation_events(
        self, limit: int = 50
    ) -> list[tuple[WallpaperHistory, Wallpaper | None]]:
        """Fetch successful and failed automatic rotation attempts."""
        return self._history_repo.get_recent_rotation_events(limit=limit)

    def get_recently_applied_wallpapers(
        self,
        limit: int = 50,
        offset: int = 0,
        monitor: str | None = None,
    ) -> list[Wallpaper]:
        """Fetch unique Wallpaper records that were applied to the desktop."""
        return self._history_repo.get_recent_wallpapers(
            limit=limit,
            offset=offset,
            monitor=monitor,
        )

    def reapply_wallpaper(
        self,
        wallpaper_id: int,
        monitor: str = "",
        style: str | None = None,
    ) -> WallpaperApplyResult:
        """Reapply a wallpaper from history to the desktop."""
        logger.info(
            "Reapplying wallpaper id=%d from history (monitor=%r, style=%r)",
            wallpaper_id,
            monitor,
            style,
        )
        return self._wp_service.set_selected_wallpaper(
            wallpaper=wallpaper_id,
            monitor=monitor,
            style=style or "Fill",
        )

    def restore_previous_wallpaper(self, monitor: str | None = None) -> WallpaperApplyResult:
        """Restore the wallpaper that was applied prior to the current desktop wallpaper."""
        logger.info("Restoring previous wallpaper (monitor=%r)", monitor)
        return self._wp_service.restore_previous_wallpaper(monitor=monitor)

    def clear_applied_history(self, monitor: str | None = None) -> int:
        """Clear desktop wallpaper application history."""
        if monitor is not None:
            cursor = self._db.execute("DELETE FROM wallpaper_history WHERE monitor = ?", (monitor,))
            self._db.commit()
            cleared = cursor.rowcount
        else:
            cleared = self._history_repo.clear()
        logger.info("Cleared applied history (monitor=%r): %d entries removed", monitor, cleared)
        return cleared

    def clear_rotation_events(self) -> int:
        """Clear automatic rotation events without changing manual history."""
        return self._history_repo.clear_rotation_events()

    def count_applied(self, monitor: str | None = None) -> int:
        """Return count of desktop application history records."""
        return self._history_repo.count(monitor=monitor)

    # ==================================================================
    # Recently Viewed Workflows
    # ==================================================================
    def record_view(self, wallpaper_id: int, timestamp: str | None = None) -> int:
        """Record a view/inspection event for a wallpaper."""
        return self._view_repo.record_view(wallpaper_id, timestamp=timestamp)

    def get_recently_viewed(self, limit: int = 50, offset: int = 0) -> list[Wallpaper]:
        """Fetch unique Wallpaper models ordered by most recent view."""
        return self._view_repo.get_recent_wallpapers(limit=limit, offset=offset)

    def clear_view_history(self) -> int:
        """Clear all wallpaper view tracking records."""
        cleared = self._view_repo.clear()
        logger.info("Cleared view history: %d entries removed.", cleared)
        return cleared

    def count_viewed(self) -> int:
        """Return total number of view events recorded."""
        return self._view_repo.count()

    def count_distinct_viewed_wallpapers(self) -> int:
        """Return number of distinct wallpapers viewed."""
        return self._view_repo.count_distinct_wallpapers()

    # ==================================================================
    # Recently Downloaded / Imported Workflows
    # ==================================================================
    def get_recently_downloaded(self, limit: int = 50, offset: int = 0) -> list[Wallpaper]:
        """Fetch wallpapers ordered by most recent download/import date."""
        return self._wp_repo.get_recently_downloaded(limit=limit, offset=offset)

    # ==================================================================
    # Summary Statistics
    # ==================================================================
    def get_history_summary(self) -> dict:
        """Return statistics summarizing favorites, applied history, and views."""
        latest_hist = self._history_repo.get_latest()
        latest_wp = self._wp_repo.get_by_id(latest_hist.wallpaper_id) if latest_hist else None

        most_used_list = self._wp_repo.get_most_used(limit=1)
        most_used = most_used_list[0] if most_used_list else None

        return {
            "favorites_count": self.count_favorites(),
            "applied_count": self.count_applied(),
            "viewed_count": self.count_viewed(),
            "distinct_viewed_count": self.count_distinct_viewed_wallpapers(),
            "latest_applied": {
                "history_id": latest_hist.id if latest_hist else None,
                "wallpaper_id": latest_hist.wallpaper_id if latest_hist else None,
                "set_at": latest_hist.set_at if latest_hist else None,
                "title": latest_wp.title if latest_wp else None,
                "filename": latest_wp.filename if latest_wp else None,
            }
            if latest_hist
            else None,
            "most_applied": {
                "wallpaper_id": most_used.id if most_used else None,
                "title": most_used.title if most_used else None,
                "usage_count": most_used.usage_count if most_used else 0,
            }
            if most_used
            else None,
        }
