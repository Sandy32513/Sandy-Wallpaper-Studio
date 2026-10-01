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

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

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

        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Connecting to database: %s", self._db_path)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        # Return rows as sqlite3.Row for dict-like access
        self._conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent read performance
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        self._conn.execute("PRAGMA foreign_keys=ON")

        logger.info("Database connected. Running migrations...")
        version = run_migrations(self._conn)
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
