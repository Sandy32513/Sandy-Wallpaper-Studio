"""
Sandy Wallpaper Studio - Database Manager
============================================
SQLite connection management and initialization.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from app.database.migrations import run_migrations

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager.

    Handles connection lifecycle, WAL mode, and migration execution.
    Thread-safety: each thread should create its own Database instance
    or use the connection carefully with check_same_thread=False.
    """

    def __init__(self, db_path: Path, *, read_only: bool = False) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._read_only = read_only

    @property
    def path(self) -> Path:
        return self._db_path

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    def connect(self) -> None:
        """Open the database connection and run migrations."""
        if self._conn is not None:
            logger.warning("Database already connected.")
            return

        if self._read_only:
            logger.info("Connecting to database in read-only mode.")
        else:
            logger.info("Connecting to database: %s", self._db_path)
        if self._read_only:
            if not self._db_path.is_file():
                raise FileNotFoundError("Read-only database file does not exist.")
            database_uri = f"{self._db_path.resolve().as_uri()}?mode=ro"
            self._conn = sqlite3.connect(
                database_uri,
                uri=True,
                check_same_thread=False,
                timeout=10.0,
            )
        else:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10.0,
            )
        # Return rows as sqlite3.Row for dict-like access
        self._conn.row_factory = sqlite3.Row

        if self._read_only:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA query_only=ON")
            return

        # Enable WAL mode for better concurrent read performance
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        self._conn.execute("PRAGMA foreign_keys=ON")

        logger.info("Database connected. Running migrations...")
        version = run_migrations(self._conn)

        # Ensure wallpaper_views table exists for backwards compatibility with earlier db versions
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS wallpaper_views (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                wallpaper_id    INTEGER NOT NULL,
                viewed_at       TEXT NOT NULL,
                FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id)
                    ON DELETE CASCADE
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_views_wallpaper_id ON wallpaper_views (wallpaper_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_views_viewed_at ON wallpaper_views (viewed_at)"
        )
        self._conn.commit()

        logger.info("Database ready at schema version %d.", version)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    def execute(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> sqlite3.Cursor:
        """Execute a SQL statement."""
        if params is None:
            return self.connection.execute(sql)
        return self.connection.execute(sql, params)

    def executemany(
        self,
        sql: str,
        params_seq: list[tuple] | list[dict],
    ) -> sqlite3.Cursor:
        """Execute a SQL statement for each set of parameters."""
        return self.connection.executemany(sql, params_seq)

    def commit(self) -> None:
        """Commit the current transaction."""
        self.connection.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self.connection.rollback()

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        if exc_type is not None:
            self.rollback()
        self.close()

    def __repr__(self) -> str:
        status = "connected" if self._conn else "disconnected"
        return f"Database(path={self._db_path!r}, status={status})"
