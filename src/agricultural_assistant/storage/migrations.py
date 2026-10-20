"""Database migration manager for Agricultural Assistant SQLite storage."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import sqlite3
from typing import Callable, List, Tuple

logger = logging.getLogger("agricultural_assistant.storage.migrations")


def migration_1_initial_observations(conn: sqlite3.Connection) -> None:
    """Create the farm_observations table and performance indexes."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS farm_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            notes TEXT NOT NULL,
            growth_stage TEXT,
            observed_at TEXT NOT NULL,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            observer_role TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_observations_crop ON farm_observations(crop);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_observations_observed_at ON farm_observations(observed_at);"
    )


def migration_2_crop_knowledge_fts(conn: sqlite3.Connection) -> None:
    """Create relational table and FTS5 virtual table for searchable crop knowledge."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crop_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            disease_name TEXT NOT NULL,
            scientific_name TEXT,
            symptoms_text TEXT NOT NULL,
            favorable_conditions_text TEXT NOT NULL,
            growth_stages_text TEXT NOT NULL,
            management_practices_json TEXT NOT NULL,
            source_reference TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'illustrative_verified',
            language TEXT NOT NULL DEFAULT 'en',
            created_at TEXT NOT NULL,
            CONSTRAINT uq_crop_disease_lang UNIQUE (crop, disease_name, language)
        );
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS crop_knowledge_fts USING fts5(
            crop,
            disease_name,
            scientific_name,
            symptoms_text,
            favorable_conditions_text,
            management_practices_json,
            content='crop_knowledge',
            content_rowid='id'
        );
        """
    )
    # Triggers to keep FTS5 synchronized with crop_knowledge table
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_crop_knowledge_ai AFTER INSERT ON crop_knowledge BEGIN
            INSERT INTO crop_knowledge_fts(rowid, crop, disease_name, scientific_name, symptoms_text, favorable_conditions_text, management_practices_json)
            VALUES (new.id, new.crop, new.disease_name, new.scientific_name, new.symptoms_text, new.favorable_conditions_text, new.management_practices_json);
        END;
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_crop_knowledge_ad AFTER DELETE ON crop_knowledge BEGIN
            INSERT INTO crop_knowledge_fts(crop_knowledge_fts, rowid, crop, disease_name, scientific_name, symptoms_text, favorable_conditions_text, management_practices_json)
            VALUES('delete', old.id, old.crop, old.disease_name, old.scientific_name, old.symptoms_text, old.favorable_conditions_text, old.management_practices_json);
        END;
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_crop_knowledge_au AFTER UPDATE ON crop_knowledge BEGIN
            INSERT INTO crop_knowledge_fts(crop_knowledge_fts, rowid, crop, disease_name, scientific_name, symptoms_text, favorable_conditions_text, management_practices_json)
            VALUES('delete', old.id, old.crop, old.disease_name, old.scientific_name, old.symptoms_text, old.favorable_conditions_text, old.management_practices_json);
            INSERT INTO crop_knowledge_fts(rowid, crop, disease_name, scientific_name, symptoms_text, favorable_conditions_text, management_practices_json)
            VALUES (new.id, new.crop, new.disease_name, new.scientific_name, new.symptoms_text, new.favorable_conditions_text, new.management_practices_json);
        END;
        """
    )


MIGRATIONS: List[Tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
    (1, "Create farm_observations table and indexes", migration_1_initial_observations),
    (2, "Create crop_knowledge and FTS5 search index", migration_2_crop_knowledge_fts),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    """Ensure the schema_migrations tracking table exists and apply all pending migrations."""
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )

        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations;")
        applied_versions = {row[0] for row in cursor.fetchall()}

        for version, description, migration_fn in MIGRATIONS:
            if version not in applied_versions:
                logger.info("Applying database migration %d: %s", version, description)
                migration_fn(conn)
                now_utc = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?);",
                    (version, description, now_utc),
                )
                logger.info("Migration %d successfully applied.", version)
