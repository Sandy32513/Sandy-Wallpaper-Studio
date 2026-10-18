"""
Sandy Wallpaper Studio - Wallpaper View Repository
===================================================
CRUD operations for the wallpaper_views table.
Tracks when wallpapers were viewed or inspected in detail.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.database.database import Database
from app.database.models import Wallpaper, WallpaperView
from app.database.wallpaper_repository import _row_to_wallpaper

logger = logging.getLogger(__name__)


def _row_to_view(row) -> WallpaperView:
    """Convert a sqlite3.Row to a WallpaperView dataclass."""
    return WallpaperView(
        id=row["id"],
        wallpaper_id=row["wallpaper_id"],
        viewed_at=row["viewed_at"],
    )


class ViewRepository:
    """Repository for wallpaper view tracking operations."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, entry: WallpaperView) -> int:
        """Insert a view record. Returns the new row ID."""
        data = entry.to_dict()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = f"INSERT INTO wallpaper_views ({columns}) VALUES ({placeholders})"

        cursor = self._db.execute(sql, data)
        self._db.commit()
        new_id = cursor.lastrowid
        logger.info(
            "Recorded wallpaper view id=%d: wallpaper_id=%d viewed_at=%s",
            new_id,
            entry.wallpaper_id,
            entry.viewed_at,
        )
        return new_id  # type: ignore[return-value]

    def record_view(self, wallpaper_id: int, timestamp: str | None = None) -> int:
        """Convenience method to record a view with current timestamp."""
        if not timestamp:
            timestamp = datetime.now(UTC).isoformat()
        entry = WallpaperView(wallpaper_id=wallpaper_id, viewed_at=timestamp)
        return self.add(entry)

    def get_by_id(self, entry_id: int) -> WallpaperView | None:
        """Fetch a single view record by ID."""
        cursor = self._db.execute("SELECT * FROM wallpaper_views WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        return _row_to_view(row) if row else None

    def get_recent(self, limit: int = 50, offset: int = 0) -> list[WallpaperView]:
        """Fetch recent view entries ordered newest first."""
        cursor = self._db.execute(
            "SELECT * FROM wallpaper_views ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [_row_to_view(r) for r in cursor.fetchall()]

    def get_recent_wallpaper_ids(self, limit: int = 50, offset: int = 0) -> list[int]:
        """Fetch distinct wallpaper IDs ordered by most recent view."""
        cursor = self._db.execute(
            """
            SELECT wallpaper_id, MAX(viewed_at) as max_viewed
            FROM wallpaper_views
            GROUP BY wallpaper_id
            ORDER BY max_viewed DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [row["wallpaper_id"] for row in cursor.fetchall()]

    def get_recent_wallpapers(self, limit: int = 50, offset: int = 0) -> list[Wallpaper]:
        """Fetch unique Wallpaper records ordered by most recent view."""
        cursor = self._db.execute(
            """
            SELECT w.*
            FROM wallpapers w
            JOIN (
                SELECT wallpaper_id, MAX(viewed_at) as max_viewed
                FROM wallpaper_views
                GROUP BY wallpaper_id
                ORDER BY max_viewed DESC
                LIMIT ? OFFSET ?
            ) v ON w.id = v.wallpaper_id
            ORDER BY v.max_viewed DESC
            """,
            (limit, offset),
        )
        return [_row_to_wallpaper(r) for r in cursor.fetchall()]

    def count(self) -> int:
        """Count total view records."""
        cursor = self._db.execute("SELECT COUNT(*) FROM wallpaper_views")
        row = cursor.fetchone()
        return row[0] if row else 0

    def count_distinct_wallpapers(self) -> int:
        """Count number of distinct wallpapers viewed."""
        cursor = self._db.execute("SELECT COUNT(DISTINCT wallpaper_id) FROM wallpaper_views")
        row = cursor.fetchone()
        return row[0] if row else 0

    def delete_for_wallpaper(self, wallpaper_id: int) -> int:
        """Delete all view entries for a given wallpaper."""
        cursor = self._db.execute(
            "DELETE FROM wallpaper_views WHERE wallpaper_id = ?",
            (wallpaper_id,),
        )
        self._db.commit()
        return cursor.rowcount

    def clear(self) -> int:
        """Clear all view records."""
        cursor = self._db.execute("DELETE FROM wallpaper_views")
        self._db.commit()
        return cursor.rowcount
