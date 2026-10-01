"""
Sandy Wallpaper Studio - Wallpaper Repository
================================================
CRUD operations for the wallpapers table.
All queries go through this layer — the UI and services never
write raw SQL against the wallpapers table directly.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.database.database import Database
from app.database.models import Wallpaper

logger = logging.getLogger(__name__)


def _row_to_wallpaper(row) -> Wallpaper:
    """Convert a sqlite3.Row to a Wallpaper dataclass."""
    return Wallpaper(
        id=row["id"],
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
        source=row["source"],
        source_url=row["source_url"],
        author=row["author"],
        license=row["license"],
        license_url=row["license_url"],
        download_date=row["download_date"],
        favorite=bool(row["favorite"]),
        last_used=row["last_used"],
        usage_count=row["usage_count"],
    )


class WallpaperRepository:
    """Repository for wallpaper CRUD operations."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ----------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------
    def add(self, wallpaper: Wallpaper) -> int:
        """Insert a new wallpaper. Returns the new row ID."""
        data = wallpaper.to_dict()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = f"INSERT INTO wallpapers ({columns}) VALUES ({placeholders})"

        cursor = self._db.execute(sql, data)
        self._db.commit()
        new_id = cursor.lastrowid
        logger.info("Added wallpaper id=%d: %s", new_id, wallpaper.filename)
        return new_id  # type: ignore[return-value]

    def add_many(self, wallpapers: list[Wallpaper]) -> int:
        """Insert multiple wallpapers. Returns the count inserted."""
        if not wallpapers:
            return 0
        data_list = [w.to_dict() for w in wallpapers]
        columns = ", ".join(data_list[0].keys())
        placeholders = ", ".join(f":{k}" for k in data_list[0].keys())
        sql = f"INSERT INTO wallpapers ({columns}) VALUES ({placeholders})"

        self._db.executemany(sql, data_list)
        self._db.commit()
        logger.info("Added %d wallpapers in batch.", len(wallpapers))
        return len(wallpapers)

    # ----------------------------------------------------------
    # READ
    # ----------------------------------------------------------
    def get_by_id(self, wallpaper_id: int) -> Optional[Wallpaper]:
        """Fetch a single wallpaper by ID."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE id = ?", (wallpaper_id,)
        )
        row = cursor.fetchone()
        return _row_to_wallpaper(row) if row else None

    def get_by_sha256(self, sha256: str) -> Optional[Wallpaper]:
        """Fetch a wallpaper by its SHA-256 hash (exact duplicate check)."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE sha256 = ?", (sha256,)
        )
        row = cursor.fetchone()
        return _row_to_wallpaper(row) if row else None

    def get_by_path(self, path: str) -> Optional[Wallpaper]:
        """Fetch a wallpaper by its file path."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE path = ?", (path,)
        )
        row = cursor.fetchone()
        return _row_to_wallpaper(row) if row else None

    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "download_date DESC",
    ) -> list[Wallpaper]:
        """Fetch wallpapers with pagination."""
        # Whitelist allowed order columns to prevent SQL injection
        allowed_orders = {
            "download_date DESC", "download_date ASC",
            "title ASC", "title DESC",
            "file_size ASC", "file_size DESC",
            "width DESC", "width ASC",
            "usage_count DESC", "usage_count ASC",
            "last_used DESC", "last_used ASC",
            "id ASC", "id DESC",
        }
        if order_by not in allowed_orders:
            order_by = "download_date DESC"

        cursor = self._db.execute(
            f"SELECT * FROM wallpapers ORDER BY {order_by} LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def get_by_category(
        self,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallpaper]:
        """Fetch wallpapers filtered by category."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE category = ? ORDER BY download_date DESC LIMIT ? OFFSET ?",
            (category, limit, offset),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def get_by_resolution_class(
        self,
        resolution_class: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallpaper]:
        """Fetch wallpapers filtered by resolution class."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE resolution_class = ? ORDER BY download_date DESC LIMIT ? OFFSET ?",
            (resolution_class, limit, offset),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def get_favorites(self, limit: int = 100, offset: int = 0) -> list[Wallpaper]:
        """Fetch favorite wallpapers."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE favorite = 1 ORDER BY download_date DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def get_recently_used(self, limit: int = 50) -> list[Wallpaper]:
        """Fetch most recently used wallpapers."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE last_used IS NOT NULL ORDER BY last_used DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def get_never_used(self, limit: int = 100, offset: int = 0) -> list[Wallpaper]:
        """Fetch wallpapers that have never been set as desktop background."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE usage_count = 0 ORDER BY download_date DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def get_most_used(self, limit: int = 50) -> list[Wallpaper]:
        """Fetch most frequently used wallpapers."""
        cursor = self._db.execute(
            "SELECT * FROM wallpapers WHERE usage_count > 0 ORDER BY usage_count DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        resolution_class: Optional[str] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        source: Optional[str] = None,
        favorites_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallpaper]:
        """Smart search with multiple filters (Section 7)."""
        conditions: list[str] = []
        params: list = []

        if query:
            # Search across title, description, tags, category, author
            conditions.append(
                "(title LIKE ? OR description LIKE ? OR tags LIKE ? "
                "OR category LIKE ? OR author LIKE ? OR filename LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like] * 6)

        if category:
            conditions.append("category = ?")
            params.append(category)

        if resolution_class:
            conditions.append("resolution_class = ?")
            params.append(resolution_class)

        if min_width is not None:
            conditions.append("width >= ?")
            params.append(min_width)

        if min_height is not None:
            conditions.append("height >= ?")
            params.append(min_height)

        if source:
            conditions.append("source = ?")
            params.append(source)

        if favorites_only:
            conditions.append("favorite = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM wallpapers WHERE {where_clause} ORDER BY download_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, tuple(params))
        return [_row_to_wallpaper(row) for row in cursor.fetchall()]

    def count(self, category: Optional[str] = None) -> int:
        """Count wallpapers, optionally filtered by category."""
        if category:
            cursor = self._db.execute(
                "SELECT COUNT(*) FROM wallpapers WHERE category = ?", (category,)
            )
        else:
            cursor = self._db.execute("SELECT COUNT(*) FROM wallpapers")
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_all_phashes(self) -> list[tuple[int, str]]:
        """Fetch all (id, phash) pairs for duplicate scanning."""
        cursor = self._db.execute(
            "SELECT id, phash FROM wallpapers WHERE phash != '' ORDER BY id"
        )
        return [(row["id"], row["phash"]) for row in cursor.fetchall()]

    def get_statistics(self) -> dict:
        """Return library statistics."""
        stats = {}
        row = self._db.execute("SELECT COUNT(*) as cnt FROM wallpapers").fetchone()
        stats["total"] = row["cnt"] if row else 0

        row = self._db.execute("SELECT COUNT(*) as cnt FROM wallpapers WHERE favorite = 1").fetchone()
        stats["favorites"] = row["cnt"] if row else 0

        row = self._db.execute("SELECT SUM(file_size) as total_size FROM wallpapers").fetchone()
        stats["total_size_bytes"] = row["total_size"] or 0

        row = self._db.execute("SELECT COUNT(DISTINCT category) as cnt FROM wallpapers WHERE category != ''").fetchone()
        stats["categories_used"] = row["cnt"] if row else 0

        row = self._db.execute("SELECT COUNT(DISTINCT source) as cnt FROM wallpapers").fetchone()
        stats["sources_used"] = row["cnt"] if row else 0

        # Resolution distribution
        cursor = self._db.execute(
            "SELECT resolution_class, COUNT(*) as cnt FROM wallpapers "
            "WHERE resolution_class != '' GROUP BY resolution_class ORDER BY cnt DESC"
        )
        stats["by_resolution"] = {r["resolution_class"]: r["cnt"] for r in cursor.fetchall()}

        return stats

    # ----------------------------------------------------------
    # UPDATE
    # ----------------------------------------------------------
    def update(self, wallpaper: Wallpaper) -> bool:
        """Update an existing wallpaper. Returns True if a row was modified."""
        if wallpaper.id is None:
            logger.error("Cannot update wallpaper without an ID.")
            return False

        data = wallpaper.to_dict()
        set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
        data["id"] = wallpaper.id
        sql = f"UPDATE wallpapers SET {set_clause} WHERE id = :id"

        cursor = self._db.execute(sql, data)
        self._db.commit()
        return cursor.rowcount > 0

    def set_favorite(self, wallpaper_id: int, favorite: bool) -> bool:
        """Toggle favorite status."""
        cursor = self._db.execute(
            "UPDATE wallpapers SET favorite = ? WHERE id = ?",
            (1 if favorite else 0, wallpaper_id),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def record_usage(self, wallpaper_id: int, timestamp: str) -> bool:
        """Record that a wallpaper was set as desktop background."""
        cursor = self._db.execute(
            "UPDATE wallpapers SET last_used = ?, usage_count = usage_count + 1 WHERE id = ?",
            (timestamp, wallpaper_id),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def update_category(self, wallpaper_id: int, category: str) -> bool:
        """Change a wallpaper's category."""
        cursor = self._db.execute(
            "UPDATE wallpapers SET category = ? WHERE id = ?",
            (category, wallpaper_id),
        )
        self._db.commit()
        return cursor.rowcount > 0

    # ----------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------
    def delete(self, wallpaper_id: int) -> bool:
        """Delete a wallpaper record. Returns True if a row was deleted.

        NOTE: This only removes the database record. File deletion
        is handled by the service layer with user confirmation.
        """
        cursor = self._db.execute(
            "DELETE FROM wallpapers WHERE id = ?", (wallpaper_id,)
        )
        self._db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted wallpaper id=%d from database.", wallpaper_id)
        return deleted
