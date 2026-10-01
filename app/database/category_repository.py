"""
Sandy Wallpaper Studio - Category Repository
===============================================
CRUD operations for the categories table.
Handles both default and user-created categories.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.constants import DEFAULT_CATEGORIES
from app.database.database import Database
from app.database.models import Category

logger = logging.getLogger(__name__)


def _row_to_category(row) -> Category:
    """Convert a sqlite3.Row to a Category dataclass."""
    return Category(
        id=row["id"],
        name=row["name"],
        is_default=bool(row["is_default"]),
        icon=row["icon"],
        sort_order=row["sort_order"],
    )


class CategoryRepository:
    """Repository for category CRUD operations."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def seed_defaults(self) -> int:
        """Insert default categories if they don't already exist.

        Returns the number of categories inserted.
        """
        inserted = 0
        for idx, name in enumerate(DEFAULT_CATEGORIES):
            try:
                self._db.execute(
                    "INSERT OR IGNORE INTO categories (name, is_default, icon, sort_order) "
                    "VALUES (?, 1, '', ?)",
                    (name, idx),
                )
                inserted += 1
            except Exception:
                pass  # Ignore duplicates
        self._db.commit()
        logger.info("Seeded %d default categories.", len(DEFAULT_CATEGORIES))
        return inserted

    # ----------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------
    def add(self, category: Category) -> int:
        """Insert a new category. Returns the new row ID."""
        data = category.to_dict()
        cursor = self._db.execute(
            "INSERT INTO categories (name, is_default, icon, sort_order) "
            "VALUES (:name, :is_default, :icon, :sort_order)",
            data,
        )
        self._db.commit()
        new_id = cursor.lastrowid
        logger.info("Added category id=%d: %s", new_id, category.name)
        return new_id  # type: ignore[return-value]

    # ----------------------------------------------------------
    # READ
    # ----------------------------------------------------------
    def get_all(self) -> list[Category]:
        """Fetch all categories, ordered by sort_order."""
        cursor = self._db.execute(
            "SELECT * FROM categories ORDER BY sort_order ASC, name ASC"
        )
        return [_row_to_category(row) for row in cursor.fetchall()]

    def get_by_name(self, name: str) -> Optional[Category]:
        """Fetch a category by name."""
        cursor = self._db.execute(
            "SELECT * FROM categories WHERE name = ?", (name,)
        )
        row = cursor.fetchone()
        return _row_to_category(row) if row else None

    def get_by_id(self, category_id: int) -> Optional[Category]:
        """Fetch a category by ID."""
        cursor = self._db.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        )
        row = cursor.fetchone()
        return _row_to_category(row) if row else None

    def get_defaults(self) -> list[Category]:
        """Fetch only default (built-in) categories."""
        cursor = self._db.execute(
            "SELECT * FROM categories WHERE is_default = 1 ORDER BY sort_order ASC"
        )
        return [_row_to_category(row) for row in cursor.fetchall()]

    def get_custom(self) -> list[Category]:
        """Fetch only user-created categories."""
        cursor = self._db.execute(
            "SELECT * FROM categories WHERE is_default = 0 ORDER BY name ASC"
        )
        return [_row_to_category(row) for row in cursor.fetchall()]

    def count(self) -> int:
        """Count total categories."""
        row = self._db.execute("SELECT COUNT(*) FROM categories").fetchone()
        return row[0] if row else 0

    # ----------------------------------------------------------
    # UPDATE
    # ----------------------------------------------------------
    def rename(self, category_id: int, new_name: str) -> bool:
        """Rename a category. Returns True if successful."""
        cursor = self._db.execute(
            "UPDATE categories SET name = ? WHERE id = ?",
            (new_name, category_id),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def update_sort_order(self, category_id: int, sort_order: int) -> bool:
        """Update a category's sort position."""
        cursor = self._db.execute(
            "UPDATE categories SET sort_order = ? WHERE id = ?",
            (sort_order, category_id),
        )
        self._db.commit()
        return cursor.rowcount > 0

    # ----------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------
    def delete(self, category_id: int) -> bool:
        """Delete a category. Returns True if deleted.

        NOTE: Wallpapers in this category keep their category string —
        they just become "uncategorized" from the UI's perspective.
        """
        cursor = self._db.execute(
            "DELETE FROM categories WHERE id = ?", (category_id,)
        )
        self._db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted category id=%d.", category_id)
        return deleted
