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
from app.database.models import Wallpaper, WallpaperHistory

logger = logging.getLogger(__name__)


def _row_to_history(row) -> WallpaperHistory:
    """Convert a sqlite3.Row to a WallpaperHistory dataclass."""
    return WallpaperHistory(
        id=row["id"],
        wallpaper_id=row["wallpaper_id"],
        set_at=row["set_at"],
        monitor=row["monitor"] if "monitor" in row.keys() else "",
        source=row["source"] if "source" in row.keys() else "manual",
        success=bool(row["success"]) if "success" in row.keys() else True,
        error_message=row["error_message"] if "error_message" in row.keys() else "",
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
                "SELECT * FROM wallpaper_history WHERE success = 1 AND monitor = ? "
                "ORDER BY id DESC LIMIT 1",
                (monitor,),
            )
        else:
            cursor = self._db.execute(
                "SELECT * FROM wallpaper_history WHERE success = 1 ORDER BY id DESC LIMIT 1"
            )
        row = cursor.fetchone()
        return _row_to_history(row) if row else None

    def get_previous(
        self,
        monitor: Optional[str] = None,
        exclude_wallpaper_id: Optional[int] = None,
    ) -> Optional[WallpaperHistory]:
        """Fetch the previous wallpaper record prior to the current/excluded one."""
        conditions: list[str] = ["success = 1"]
        params: list = []

        if monitor is not None:
            conditions.append("monitor = ?")
            params.append(monitor)

        if exclude_wallpaper_id is not None:
            conditions.append("wallpaper_id != ?")
            params.append(exclude_wallpaper_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM wallpaper_history {where_clause} ORDER BY id DESC LIMIT 1"
        cursor = self._db.execute(sql, tuple(params))
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
                "SELECT * FROM wallpaper_history WHERE success = 1 AND monitor = ? "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (monitor, limit, offset),
            )
        else:
            cursor = self._db.execute(
                "SELECT * FROM wallpaper_history WHERE success = 1 "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [_row_to_history(r) for r in cursor.fetchall()]

    def get_recent_with_wallpapers(
        self,
        limit: int = 50,
        offset: int = 0,
        monitor: Optional[str] = None,
    ) -> list[tuple[WallpaperHistory, Optional[Wallpaper]]]:
        """Fetch recent history entries joined with their Wallpaper models."""
        conditions: list[str] = ["h.success = 1"]
        params: list = []
        if monitor is not None:
            conditions.append("h.monitor = ?")
            params.append(monitor)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT h.*, w.id as wp_id, w.filename, w.path, w.title, w.description,
                   w.category, w.tags, w.width, w.height, w.aspect_ratio,
                   w.resolution_class, w.file_size, w.sha256, w.phash,
                   w.source, w.source_url, w.author, w.license, w.license_url,
                   w.download_date, w.favorite, w.last_used, w.usage_count
            FROM wallpaper_history h
            LEFT JOIN wallpapers w ON h.wallpaper_id = w.id
            {where_clause}
            ORDER BY h.id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        cursor = self._db.execute(sql, tuple(params))
        results = []
        for r in cursor.fetchall():
            hist = _row_to_history(r)
            if r["wp_id"] is not None:
                wp = Wallpaper(
                    id=r["wp_id"],
                    filename=r["filename"],
                    path=r["path"],
                    title=r["title"],
                    description=r["description"],
                    category=r["category"],
                    tags=r["tags"],
                    width=r["width"],
                    height=r["height"],
                    aspect_ratio=r["aspect_ratio"],
                    resolution_class=r["resolution_class"],
                    file_size=r["file_size"],
                    sha256=r["sha256"],
                    phash=r["phash"],
                    source=r["source"],
                    source_url=r["source_url"],
                    author=r["author"],
                    license=r["license"],
                    license_url=r["license_url"],
                    download_date=r["download_date"],
                    favorite=bool(r["favorite"]),
                    last_used=r["last_used"],
                    usage_count=r["usage_count"],
                )
            else:
                wp = None
            results.append((hist, wp))
        return results

    def get_recent_wallpapers(
        self,
        limit: int = 50,
        offset: int = 0,
        monitor: Optional[str] = None,
    ) -> list[Wallpaper]:
        """Fetch unique Wallpaper records ordered by most recently applied."""
        from app.database.wallpaper_repository import _row_to_wallpaper

        conditions: list[str] = ["h.success = 1"]
        params: list = []
        if monitor is not None:
            conditions.append("h.monitor = ?")
            params.append(monitor)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT w.*
            FROM wallpapers w
            JOIN (
                SELECT h.wallpaper_id, MAX(h.id) as max_hid
                FROM wallpaper_history h
                {where_clause}
                GROUP BY h.wallpaper_id
                ORDER BY max_hid DESC
                LIMIT ? OFFSET ?
            ) sub ON w.id = sub.wallpaper_id
            ORDER BY sub.max_hid DESC
        """
        params.extend([limit, offset])
        cursor = self._db.execute(sql, tuple(params))
        return [_row_to_wallpaper(r) for r in cursor.fetchall()]

    def count(self, monitor: Optional[str] = None) -> int:
        """Count total history records."""
        if monitor is not None:
            cursor = self._db.execute(
                "SELECT COUNT(*) FROM wallpaper_history WHERE success = 1 AND monitor = ?",
                (monitor,),
            )
        else:
            cursor = self._db.execute("SELECT COUNT(*) FROM wallpaper_history WHERE success = 1")
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

    def clear_rotation_events(self) -> int:
        """Clear rotation attempts while preserving manual application history."""
        cursor = self._db.execute(
            "DELETE FROM wallpaper_history WHERE source = 'rotation'"
        )
        self._db.commit()
        return cursor.rowcount

    def get_recent_rotation_events(
        self, limit: int = 50
    ) -> list[tuple[WallpaperHistory, Optional[Wallpaper]]]:
        """Fetch automatic rotation attempts, including unsuccessful attempts."""
        sql = """
            SELECT h.*, w.id as wp_id, w.filename, w.path, w.title, w.description,
                   w.category, w.tags, w.width, w.height, w.aspect_ratio,
                   w.resolution_class, w.file_size, w.sha256, w.phash,
                   w.source as wallpaper_source, w.source_url, w.author, w.license,
                   w.license_url, w.download_date, w.favorite, w.last_used, w.usage_count
            FROM wallpaper_history h
            LEFT JOIN wallpapers w ON h.wallpaper_id = w.id
            WHERE h.source = 'rotation'
            ORDER BY h.id DESC
            LIMIT ?
        """
        cursor = self._db.execute(sql, (limit,))
        results: list[tuple[WallpaperHistory, Optional[Wallpaper]]] = []
        for row in cursor.fetchall():
            history = _row_to_history(row)
            wallpaper = None
            if row["wp_id"] is not None:
                wallpaper = Wallpaper(
                    id=row["wp_id"],
                    filename=row["filename"],
                    path=row["path"],
                    title=row["title"],
                    description=row["description"],
                    category=row["category"],
                    tags=row["tags"],
                    width=row["width"],
                    height=row["height"],
                    aspect_ratio=row["aspect_ratio"],
                    resolution_class=row["resolution_class"],
                    file_size=row["file_size"],
                    sha256=row["sha256"],
                    phash=row["phash"],
                    source=row["wallpaper_source"],
                    source_url=row["source_url"],
                    author=row["author"],
                    license=row["license"],
                    license_url=row["license_url"],
                    download_date=row["download_date"],
                    favorite=bool(row["favorite"]),
                    last_used=row["last_used"],
                    usage_count=row["usage_count"],
                )
            results.append((history, wallpaper))
        return results
