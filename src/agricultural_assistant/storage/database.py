"""Database connection and lifecycle manager for SQLite persistence."""

from __future__ import annotations

from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from typing import Generator, Optional, Union

from agricultural_assistant.config import get_settings
from agricultural_assistant.storage.migrations import run_migrations

logger = logging.getLogger("agricultural_assistant.storage.database")


class DatabaseManager:
    """Manages SQLite connections, transactions, and migration execution."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None:
            settings = get_settings()
            self.db_path = Path(settings.database_path)
        elif str(db_path) == ":memory:":
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)

        self._is_memory = str(self.db_path) == ":memory:"
        self._shared_memory_conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Create parent directory and apply pending schema migrations."""
        if not self._is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            run_migrations(conn)
        logger.debug("Database initialized at %s", self.db_path)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a contextual database connection with automatic commit and rollback."""
        if self._is_memory:
            if self._shared_memory_conn is None:
                self._shared_memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._shared_memory_conn.row_factory = sqlite3.Row
            conn = self._shared_memory_conn
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            return

        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def backup(self, destination_path: Union[str, Path]) -> Path:
        """Create a consistent point-in-time online backup using SQLite's native backup API."""
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as src_conn:
            with sqlite3.connect(str(dest)) as dest_conn:
                src_conn.backup(dest_conn)
        logger.info("Database backup created successfully at %s", dest)
        return dest

    def restore(self, backup_path: Union[str, Path]) -> None:
        """Restore database state from a validated backup file using SQLite's native backup API."""
        src = Path(backup_path)
        if not src.exists():
            raise FileNotFoundError(f"Backup file not found at {src}")

        with sqlite3.connect(str(src)) as bkp_conn:
            with self.get_connection() as target_conn:
                bkp_conn.backup(target_conn)
        logger.info("Database restored successfully from %s", src)

    def close(self) -> None:
        """Close shared in-memory connection if active."""
        if self._shared_memory_conn is not None:
            try:
                self._shared_memory_conn.close()
            except Exception as exc:
                logger.debug("Error closing in-memory connection: %s", exc)
            self._shared_memory_conn = None
