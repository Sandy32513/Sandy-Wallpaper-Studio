"""
Sandy Wallpaper Studio - Database Migrations
===============================================
Schema versioning and migration system for SQLite.
Each migration is a function that receives a cursor and applies DDL.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Callable

logger = logging.getLogger(__name__)

# Type alias for a migration function
MigrationFn = Callable[[sqlite3.Cursor], None]


# ============================================================
# Migration Registry
# ============================================================
# Each entry: (version_number, description, migration_function)
# Versions must be sequential starting from 1.

def _migration_001_initial_schema(cursor: sqlite3.Cursor) -> None:
    """Create the initial database schema."""

    # --- Wallpapers table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallpapers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT    NOT NULL DEFAULT '',
            path            TEXT    NOT NULL DEFAULT '',
            title           TEXT    NOT NULL DEFAULT '',
            description     TEXT    NOT NULL DEFAULT '',
            category        TEXT    NOT NULL DEFAULT '',
            tags            TEXT    NOT NULL DEFAULT '',
            width           INTEGER NOT NULL DEFAULT 0,
            height          INTEGER NOT NULL DEFAULT 0,
            aspect_ratio    TEXT    NOT NULL DEFAULT '',
            resolution_class TEXT   NOT NULL DEFAULT '',
            file_size       INTEGER NOT NULL DEFAULT 0,
            sha256          TEXT    NOT NULL DEFAULT '',
            phash           TEXT    NOT NULL DEFAULT '',
            source          TEXT    NOT NULL DEFAULT '',
            source_url      TEXT    NOT NULL DEFAULT '',
            author          TEXT    NOT NULL DEFAULT '',
            license         TEXT    NOT NULL DEFAULT '',
            license_url     TEXT    NOT NULL DEFAULT '',
            download_date   TEXT,
            favorite        INTEGER NOT NULL DEFAULT 0,
            last_used       TEXT,
            usage_count     INTEGER NOT NULL DEFAULT 0
        )
    """)

    # --- Indexes (Section 23) ---
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_sha256 ON wallpapers (sha256)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_phash ON wallpapers (phash)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_category ON wallpapers (category)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_resolution_class ON wallpapers (resolution_class)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_favorite ON wallpapers (favorite)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_download_date ON wallpapers (download_date)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_source ON wallpapers (source)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallpapers_last_used ON wallpapers (last_used)"
    )

    # --- Categories table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            is_default  INTEGER NOT NULL DEFAULT 1,
            icon        TEXT    NOT NULL DEFAULT '',
            sort_order  INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_name ON categories (name)"
    )

    # --- Download records table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wallpaper_id    INTEGER,
            source          TEXT    NOT NULL DEFAULT '',
            source_url      TEXT    NOT NULL DEFAULT '',
            status          TEXT    NOT NULL DEFAULT 'pending',
            error_message   TEXT    NOT NULL DEFAULT '',
            started_at      TEXT,
            completed_at    TEXT,
            file_size       INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id)
                ON DELETE SET NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_downloads_status ON download_records (status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_downloads_wallpaper_id ON download_records (wallpaper_id)"
    )

    # --- Wallpaper history table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallpaper_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wallpaper_id    INTEGER NOT NULL,
            set_at          TEXT,
            monitor         TEXT    NOT NULL DEFAULT '',
            FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id)
                ON DELETE CASCADE
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_wallpaper_id ON wallpaper_history (wallpaper_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_set_at ON wallpaper_history (set_at)"
    )

    # --- Schema version table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT ''
        )
    """)

    logger.info("Migration 001: Initial schema created.")


# ============================================================
# Migration Registry
# ============================================================
MIGRATIONS: list[tuple[int, str, MigrationFn]] = [
    (1, "Initial schema", _migration_001_initial_schema),
]


# ============================================================
# Migration Runner
# ============================================================
def get_current_version(cursor: sqlite3.Cursor) -> int:
    """Return the current schema version, or 0 if uninitialized."""
    try:
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations. Returns the final schema version."""
    cursor = conn.cursor()
    current = get_current_version(cursor)
    applied = 0

    for version, description, migrate_fn in MIGRATIONS:
        if version > current:
            logger.info("Applying migration %d: %s", version, description)
            migrate_fn(cursor)
            from datetime import datetime, timezone
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (version, datetime.now(timezone.utc).isoformat(), description),
            )
            conn.commit()
            applied += 1
            logger.info("Migration %d applied successfully.", version)

    final_version = get_current_version(cursor)
    if applied == 0:
        logger.info("Database is up to date (version %d).", final_version)
    else:
        logger.info("Applied %d migration(s). Now at version %d.", applied, final_version)

    return final_version
