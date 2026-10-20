"""Unit tests for SQLite DatabaseManager, transactions, and persistence."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import pytest

from agricultural_assistant.storage.database import DatabaseManager


class TestDatabaseManager:
    """Test suite for SQLite connection management and migration lifecycle."""

    def test_in_memory_initialization(self) -> None:
        """Verify in-memory database initializes schema migrations."""
        db = DatabaseManager(":memory:")
        db.initialize()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            assert "schema_migrations" in tables
            assert "farm_observations" in tables
            assert "crop_knowledge" in tables

    def test_file_database_persistence(self, tmp_path: Path) -> None:
        """Verify records persist across separate database connection sessions."""
        db_path = tmp_path / "test_persist.db"

        # Session 1: Initialize and insert a row
        db1 = DatabaseManager(db_path)
        db1.initialize()
        with db1.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO farm_observations (
                    crop, notes, growth_stage, observed_at, location_name,
                    latitude, longitude, observer_role, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                ("teff", "Rust observed on field 1", "heading", "2026-10-20T10:00:00Z", "Plot A", 9.02, 38.74, "farmer", "2026-10-20T10:05:00Z"),
            )

        # Session 2: Reopen file with a new DatabaseManager instance
        db2 = DatabaseManager(db_path)
        with db2.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT crop, notes FROM farm_observations;")
            row = cursor.fetchone()
            assert row is not None
            assert row["crop"] == "teff"
            assert row["notes"] == "Rust observed on field 1"

    def test_transaction_rollback_on_error(self, tmp_path: Path) -> None:
        """Verify transaction rolls back uncommitted changes when an exception is raised."""
        db_path = tmp_path / "test_rollback.db"
        db = DatabaseManager(db_path)
        db.initialize()

        with pytest.raises(RuntimeError):
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO farm_observations (crop, notes, observed_at, created_at) VALUES (?, ?, ?, ?);",
                    ("maize", "Initial note", "2026-10-20T10:00:00Z", "2026-10-20T10:00:00Z"),
                )
                raise RuntimeError("Simulated crash before transaction commit")

        # Confirm the row was not committed
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM farm_observations;")
            count = cursor.fetchone()[0]
            assert count == 0

    def test_database_backup_and_restore(self, tmp_path: Path) -> None:
        """Verify SQLite online backup and restore accurately preserve records."""
        original_db = tmp_path / "original.db"
        backup_file = tmp_path / "backup.db"
        restored_db = tmp_path / "restored.db"

        # 1. Initialize original database and insert test record
        db = DatabaseManager(original_db)
        db.initialize()
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO farm_observations (crop, notes, observed_at, created_at)
                VALUES ('Coffee', 'Healthy vegetative development', '2026-10-20T10:00:00Z', '2026-10-20T10:00:00Z');
                """
            )

        # 2. Perform online point-in-time backup
        result_path = db.backup(backup_file)
        assert result_path.exists()
        assert result_path.stat().st_size > 0

        # 3. Restore into a new empty database instance
        new_db = DatabaseManager(restored_db)
        new_db.restore(backup_file)

        # 4. Verify restored database has identical record
        with new_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT crop, notes FROM farm_observations;")
            row = cursor.fetchone()
            assert row is not None
            assert row["crop"] == "Coffee"
            assert row["notes"] == "Healthy vegetative development"
