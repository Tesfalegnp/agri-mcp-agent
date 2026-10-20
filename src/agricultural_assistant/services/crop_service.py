"""Agronomic service for searching crop diseases and pest management guidelines."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agricultural_assistant.data.crop_knowledge import (
    CROP_DISEASE_DATABASE,
    DIAGNOSTIC_DISCLAIMER,
    CropDiseaseRecord,
)
from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery


class CropService:
    """Service to query curated crop disease records against reported symptoms."""

    def __init__(
        self,
        database: Optional[List[CropDiseaseRecord]] = None,
        knowledge_repository: Optional[Any] = None,
    ) -> None:
        self.database = database if database is not None else CROP_DISEASE_DATABASE
        self.knowledge_repository = knowledge_repository
        if self.knowledge_repository is not None:
            try:
                if self.knowledge_repository.count_records() == 0:
                    self.knowledge_repository.seed_default_knowledge(self.database)
            except Exception:
                pass

    def search_disease(
        self, query: CropSymptomQuery, language: str = "en"
    ) -> Dict[str, Any]:
        """Search agricultural knowledge records matching the symptom query.

        Args:
            query: Validated CropSymptomQuery object.
            language: ISO language code (defaults to 'en').

        Returns:
            Structured dictionary containing matched records, recommendations,
            and safety disclaimers.
        """
        # If SQLite FTS5 repository is provided, use it
        if self.knowledge_repository is not None:
            stage_str = (
                query.growth_stage.value
                if isinstance(query.growth_stage, CropGrowthStage)
                else (str(query.growth_stage) if query.growth_stage else None)
            )
            fts_matches = self.knowledge_repository.search_knowledge(
                crop=query.crop_name,
                query_text=query.symptoms,
                growth_stage=stage_str,
                language=language,
                limit=3,
            )
            has_matches = len(fts_matches) > 0
            message = (
                f"Found {len(fts_matches)} potential disease match(es) for '{query.crop_name}'."
                if has_matches
                else (
                    f"No specific disease matches were found in the curated database for '{query.crop_name}' "
                    f"matching the reported symptoms. The symptoms may be related to nutrient deficiency, "
                    f"abiotic stress, or a condition not yet recorded. Consultation with a local extension agent is advised."
                )
            )
            return {
                "status": "success",
                "crop": query.crop_name,
                "reported_symptoms": query.symptoms,
                "growth_stage": query.growth_stage.value if query.growth_stage else None,
                "location_context": query.location_context,
                "match_count": len(fts_matches),
                "message": message,
                "potential_matches": fts_matches,
                "diagnostic_disclaimer": DIAGNOSTIC_DISCLAIMER,
            }

        # Fallback to in-memory algorithm
        target_crop = query.crop_name.strip().lower()
        symptom_tokens = self._tokenize(query.symptoms)

        scored_records: List[tuple[int, CropDiseaseRecord]] = []

        for record in self.database:
            if record.crop.lower() not in target_crop and target_crop not in record.crop.lower():
                continue

            score = 0
            record_symptom_text = " ".join(record.common_symptoms).lower()
            record_condition_text = " ".join(record.favorable_conditions).lower()
            all_record_text = f"{record_symptom_text} {record_condition_text}"

            for token in symptom_tokens:
                if token in all_record_text:
                    score += 2

            if query.growth_stage:
                stage_val = (
                    query.growth_stage.value
                    if isinstance(query.growth_stage, CropGrowthStage)
                    else str(query.growth_stage).lower()
                )
                if any(stage_val == s.lower() for s in record.growth_stages):
                    score += 3

            if query.location_context:
                loc_tokens = self._tokenize(query.location_context)
                for loc_token in loc_tokens:
                    if loc_token in all_record_text:
                        score += 1

            if score > 0:
                scored_records.append((score, record))

        scored_records.sort(key=lambda item: item[0], reverse=True)

        matched_results: List[Dict[str, Any]] = []
        for score, rec in scored_records[:3]:
            matched_results.append(
                {
                    "disease_name": rec.disease_name,
                    "scientific_name": rec.scientific_name,
                    "relevance_score": score,
                    "common_symptoms": rec.common_symptoms,
                    "favorable_conditions": rec.favorable_conditions,
                    "affected_growth_stages": rec.growth_stages,
                    "management_recommendations": rec.management_practices,
                    "source_reference": rec.source_notes,
                    "verification_status": "illustrative_verified",
                    "language": "en",
                }
            )

        has_matches = len(matched_results) > 0
        message = (
            f"Found {len(matched_results)} potential disease match(es) for '{query.crop_name}'."
            if has_matches
            else (
                f"No specific disease matches were found in the curated database for '{query.crop_name}' "
                f"matching the reported symptoms. The symptoms may be related to nutrient deficiency, "
                f"abiotic stress, or a condition not yet recorded. Consultation with a local extension agent is advised."
            )
        )

        return {
            "status": "success",
            "crop": query.crop_name,
            "reported_symptoms": query.symptoms,
            "growth_stage": query.growth_stage.value if query.growth_stage else None,
            "location_context": query.location_context,
            "match_count": len(matched_results),
            "message": message,
            "potential_matches": matched_results,
            "diagnostic_disclaimer": DIAGNOSTIC_DISCLAIMER,
        }

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Extract lowercase alphanumeric tokens, filtering common short stop words."""
        stop_words = {
            "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
            "a", "an", "is", "are", "was", "were", "it", "its", "by", "from",
            "as", "that", "this", "these", "those", "have", "has", "had"
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        return [w for w in words if w not in stop_words]
