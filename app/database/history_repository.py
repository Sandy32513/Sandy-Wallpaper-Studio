"""
Sandy Wallpaper Studio - Wallpaper History Repository
======================================================
CRUD operations for the wallpaper_history table.
Tracks when wallpapers were applied to the desktop and on which monitor.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.database.database import Database
from app.database.models import WallpaperHistory

logger = logging.getLogger(__name__)


def _row_to_history(row) -> WallpaperHistory:
    """Convert a sqlite3.Row to a WallpaperHistory dataclass."""
    return WallpaperHistory(
        id=row["id"],
        wallpaper_id=row["wallpaper_id"],
        set_at=row["set_at"],
        monitor=row["monitor"] if "monitor" in row.keys() else "",
    )


class HistoryRepository:
    """Repository for wallpaper history operations."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, entry: WallpaperHistory) -> int:
        """Insert a history record. Returns the new row ID."""
        data = entry.to_dict()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = f"INSERT INTO wallpaper_history ({columns}) VALUES ({placeholders})"

        cursor = self._db.execute(sql, data)
        self._db.commit()
        new_id = cursor.lastrowid
        logger.info(
            "Recorded wallpaper history id=%d: wallpaper_id=%d monitor=%r",
            new_id,
            entry.wallpaper_id,
            entry.monitor,
        )
        return new_id  # type: ignore[return-value]

    def get_by_id(self, entry_id: int) -> Optional[WallpaperHistory]:
        """Fetch a single history record by ID."""
        cursor = self._db.execute(
            "SELECT * FROM wallpaper_history WHERE id = ?", (entry_id,)
        )
        row = cursor.fetchone()
        return _row_to_history(row) if row else None

    def get_latest(self, monitor: Optional[str] = None) -> Optional[WallpaperHistory]:
        """Fetch the most recently set wallpaper history record."""
        if monitor is not None:
            cursor = self._db.execute(
                "SELECT * FROM wallpaper_history WHERE monitor = ? ORDER BY id DESC LIMIT 1",
                (monitor,),
            )
        else:
            cursor = self._db.execute(
                "SELECT * FROM wallpaper_history ORDER BY id DESC LIMIT 1"
            )
        row = cursor.fetchone()
        return _row_to_history(row) if row else None

    def get_previous(
        self,
        monitor: Optional[str] = None,
        exclude_wallpaper_id: Optional[int] = None,
    ) -> Optional[WallpaperHistory]:
        """Fetch the previous wallpaper record prior to the current/excluded one."""
        conditions: list[str] = []
        params: list = []

        if monitor is not None:
            conditions.append("monitor = ?")
            params.append(monitor)

        if exclude_wallpaper_id is not None:
            conditions.append("wallpaper_id != ?")
            params.append(exclude_wallpaper_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM wallpaper_history {where_clause} ORDER BY id DESC LIMIT 1"
        cursor = self._db.execute(sql, params)
        row = cursor.fetchone()
        return _row_to_history(row) if row else None

    def get_recent(
        self,
        limit: int = 50,
        offset: int = 0,
        monitor: Optional[str] = None,
    ) -> list[WallpaperHistory]:
        """Fetch recent history entries ordered newest first."""
        if monitor is not None:
            cursor = self._db.execute(
                "SELECT * FROM wallpaper_history WHERE monitor = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (monitor, limit, offset),
            )
        else:
            cursor = self._db.execute(
                "SELECT * FROM wallpaper_history ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [_row_to_history(r) for r in cursor.fetchall()]

    def count(self, monitor: Optional[str] = None) -> int:
        """Count total history records."""
        if monitor is not None:
            cursor = self._db.execute(
                "SELECT COUNT(*) FROM wallpaper_history WHERE monitor = ?", (monitor,)
            )
        else:
            cursor = self._db.execute("SELECT COUNT(*) FROM wallpaper_history")
        row = cursor.fetchone()
        return row[0] if row else 0

    def delete_for_wallpaper(self, wallpaper_id: int) -> int:
        """Delete all history entries for a given wallpaper."""
        cursor = self._db.execute(
            "DELETE FROM wallpaper_history WHERE wallpaper_id = ?", (wallpaper_id,)
        )
        self._db.commit()
        return cursor.rowcount

    def clear(self) -> int:
        """Clear all wallpaper history records."""
        cursor = self._db.execute("DELETE FROM wallpaper_history")
        self._db.commit()
        return cursor.rowcount
