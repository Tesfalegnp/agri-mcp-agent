"""Knowledge repository backed by SQLite and FTS5 full-text search index."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional

from agricultural_assistant.data.crop_knowledge import CROP_DISEASE_DATABASE, CropDiseaseRecord
from agricultural_assistant.storage.database import DatabaseManager

logger = logging.getLogger("agricultural_assistant.storage.knowledge_repository")


class KnowledgeRepository:
    """Manages persistence, seeding, and FTS5 search queries for crop knowledge."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def seed_default_knowledge(self, records: Optional[List[CropDiseaseRecord]] = None) -> int:
        """Seed initial curated records into the database, ignoring existing duplicates.

        Returns:
            Number of newly inserted records.
        """
        seed_records = records if records is not None else CROP_DISEASE_DATABASE
        now_utc = datetime.now(timezone.utc).isoformat()
        inserted_count = 0

        query = """
        INSERT OR IGNORE INTO crop_knowledge (
            crop, disease_name, scientific_name, symptoms_text,
            favorable_conditions_text, growth_stages_text,
            management_practices_json, source_reference,
            verification_status, language, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            for rec in seed_records:
                cursor.execute(
                    query,
                    (
                        rec.crop.lower(),
                        rec.disease_name,
                        rec.scientific_name,
                        " ".join(rec.common_symptoms),
                        " ".join(rec.favorable_conditions),
                        ",".join(rec.growth_stages),
                        json.dumps(rec.management_practices),
                        rec.source_notes,
                        "illustrative_verified",
                        "en",
                        now_utc,
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_count += 1

        logger.debug("Seeded %d new crop knowledge records.", inserted_count)
        return inserted_count

    def search_knowledge(
        self,
        crop: str,
        query_text: str,
        growth_stage: Optional[str] = None,
        language: str = "en",
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search agricultural knowledge records using FTS5 and token matching.

        Args:
            crop: Crop name (e.g. 'maize', 'teff').
            query_text: User-reported symptom description.
            growth_stage: Optional phenological growth stage.
            language: ISO language code ('en', 'am', 'om', 'ti').
            limit: Maximum records to return.

        Returns:
            Ranked list of matched knowledge dictionaries.
        """
        clean_crop = crop.strip().lower()
        # Sanitize query for FTS tokens
        clean_tokens = re.findall(r"\b[a-zA-Z]{3,}\b", query_text.lower())
        stop_words = {
            "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
            "a", "an", "is", "are", "was", "were", "it", "its", "by", "from"
        }
        filtered_tokens = [t for t in clean_tokens if t not in stop_words]

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # First attempt: Try FTS5 matching if tokens exist
            records: List[Dict[str, Any]] = []
            if filtered_tokens:
                fts_query = " OR ".join(filtered_tokens)
                sql = """
                SELECT k.id, k.crop, k.disease_name, k.scientific_name,
                       k.symptoms_text, k.favorable_conditions_text,
                       k.growth_stages_text, k.management_practices_json,
                       k.source_reference, k.verification_status, k.language,
                       bm25(crop_knowledge_fts) as rank
                FROM crop_knowledge_fts fts
                JOIN crop_knowledge k ON fts.rowid = k.id
                WHERE (LOWER(k.crop) = ? OR LOWER(k.crop) LIKE ?)
                  AND k.language = ?
                  AND crop_knowledge_fts MATCH ?
                ORDER BY rank ASC
                LIMIT ?;
                """
                try:
                    cursor.execute(sql, (clean_crop, f"%{clean_crop}%", language, fts_query, limit))
                    rows = cursor.fetchall()
                    for r in rows:
                        records.append(self._row_to_dict(r, score=abs(float(r["rank"]))))
                except sqlite3.OperationalError as exc:
                    logger.debug("FTS5 query failed, falling back to substring search: %s", exc)

            # Fallback or supplemental: If FTS returned nothing, check crop table directly
            if not records:
                sql_fallback = """
                SELECT id, crop, disease_name, scientific_name,
                       symptoms_text, favorable_conditions_text,
                       growth_stages_text, management_practices_json,
                       source_reference, verification_status, language
                FROM crop_knowledge
                WHERE (LOWER(crop) = ? OR LOWER(crop) LIKE ?)
                  AND language = ?;
                """
                cursor.execute(sql_fallback, (clean_crop, f"%{clean_crop}%", language))
                all_crop_rows = cursor.fetchall()

                scored_fallback: List[tuple[int, Any]] = []
                for r in all_crop_rows:
                    content = (
                        r["symptoms_text"].lower()
                        + " "
                        + r["favorable_conditions_text"].lower()
                    )
                    score = sum(2 for t in filtered_tokens if t in content)
                    if growth_stage and growth_stage.lower() in r["growth_stages_text"].lower():
                        score += 3
                    if score > 0:
                        scored_fallback.append((score, r))

                scored_fallback.sort(key=lambda x: x[0], reverse=True)
                for score, r in scored_fallback[:limit]:
                    records.append(self._row_to_dict(r, score=float(score)))

            return records

    def reindex(self) -> None:
        """Rebuild the FTS5 full-text index from the relational crop_knowledge table."""
        with self.db_manager.get_connection() as conn:
            conn.execute("INSERT INTO crop_knowledge_fts(crop_knowledge_fts) VALUES('rebuild');")
        logger.info("FTS5 crop_knowledge_fts index rebuilt successfully.")

    def count_records(self, language: Optional[str] = None) -> int:
        """Count total knowledge entries in the database."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            if language:
                cursor.execute("SELECT COUNT(*) FROM crop_knowledge WHERE language = ?;", (language,))
            else:
                cursor.execute("SELECT COUNT(*) FROM crop_knowledge;")
            res = cursor.fetchone()
            return res[0] if res else 0

    @staticmethod
    def _row_to_dict(row: Any, score: float = 0.0) -> Dict[str, Any]:
        """Convert a database row into a structured output dictionary."""
        try:
            recs = json.loads(row["management_practices_json"])
        except Exception:
            recs = [row["management_practices_json"]]

        # Parse symptoms and stages
        symptoms = [s.strip() for s in row["symptoms_text"].split("  ") if s.strip()] or [row["symptoms_text"]]
        conditions = [c.strip() for c in row["favorable_conditions_text"].split("  ") if c.strip()] or [row["favorable_conditions_text"]]
        stages = [st.strip() for st in row["growth_stages_text"].split(",") if st.strip()]

        return {
            "disease_name": row["disease_name"],
            "scientific_name": row["scientific_name"],
            "relevance_score": round(score, 2),
            "common_symptoms": symptoms,
            "favorable_conditions": conditions,
            "affected_growth_stages": stages,
            "management_recommendations": recs,
            "source_reference": row["source_reference"],
            "verification_status": row["verification_status"],
            "language": row["language"],
        }
