"""Unit tests for SQLite FTS5 KnowledgeRepository."""

from __future__ import annotations

from pathlib import Path
import pytest

from agricultural_assistant.data.crop_knowledge import CropDiseaseRecord
from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery
from agricultural_assistant.services.crop_service import CropService
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.knowledge_repository import KnowledgeRepository


class TestKnowledgeRepository:
    """Test suite for FTS5 full-text search knowledge repository."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> KnowledgeRepository:
        db_path = tmp_path / "knowledge_test.db"
        db = DatabaseManager(db_path)
        db.initialize()
        repo = KnowledgeRepository(db)
        repo.seed_default_knowledge()
        return repo

    def test_seeding_and_duplicate_prevention(self, repo: KnowledgeRepository) -> None:
        """Verify initial seed populates records and second seed does not create duplicates."""
        initial_count = repo.count_records()
        assert initial_count > 0

        # Reseed again
        new_inserted = repo.seed_default_knowledge()
        assert new_inserted == 0
        assert repo.count_records() == initial_count

    def test_fts5_search_maize_fall_armyworm(self, repo: KnowledgeRepository) -> None:
        """Verify FTS5 search matches Fall Armyworm with keywords."""
        results = repo.search_knowledge(
            crop="maize",
            query_text="ragged holes in whorl with caterpillars and frass",
        )
        assert len(results) >= 1
        assert "Fall Armyworm" in results[0]["disease_name"]
        assert results[0]["relevance_score"] >= 0
        assert results[0]["language"] == "en"
        assert results[0]["verification_status"] == "illustrative_verified"

    def test_fts5_search_coffee_berry_disease(self, repo: KnowledgeRepository) -> None:
        """Verify FTS5 search matches Coffee Berry Disease."""
        results = repo.search_knowledge(
            crop="coffee",
            query_text="dark sunken necrotic lesions on green berries",
        )
        assert len(results) >= 1
        assert "Coffee Berry Disease" in results[0]["disease_name"]
        assert results[0]["scientific_name"] == "Colletotrichum kahawae"

    def test_search_unmatched_crop_or_symptoms(self, repo: KnowledgeRepository) -> None:
        """Verify search with completely unrelated symptoms returns empty list."""
        results = repo.search_knowledge(
            crop="teff",
            query_text="unrelated metallic blue glowing crystals",
        )
        assert len(results) == 0

        # Also verify unmatched crop returns empty list
        unmatched_crop = repo.search_knowledge(
            crop="banana",
            query_text="yellowing leaves with brown spots",
        )
        assert len(unmatched_crop) == 0

    def test_reindex_execution(self, repo: KnowledgeRepository) -> None:
        """Verify rebuilding the FTS5 index runs without error and preserves searchability."""
        repo.reindex()
        results = repo.search_knowledge(
            crop="teff",
            query_text="orange rust pustules on leaves",
        )
        assert len(results) >= 1
        assert "Teff Leaf Rust" in results[0]["disease_name"]

    def test_crop_service_integrated_with_knowledge_repository(
        self, repo: KnowledgeRepository
    ) -> None:
        """Verify CropService delegates seamlessly to KnowledgeRepository."""
        service = CropService(knowledge_repository=repo)
        query = CropSymptomQuery(
            crop_name="Wheat",
            symptoms="Yellow stripe rust pustules on highland foliage",
            growth_stage=CropGrowthStage.TILLERING,
        )
        res = service.search_disease(query)
        assert res["status"] == "success"
        assert res["match_count"] >= 1
        assert "Yellow Rust" in res["potential_matches"][0]["disease_name"]
