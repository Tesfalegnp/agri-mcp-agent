"""Unit tests for the SQLite ObservationRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from agricultural_assistant.domain.crop import CropGrowthStage
from agricultural_assistant.domain.observation import FarmObservation
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.observation_repository import ObservationRepository


class TestObservationRepository:
    """Test suite for observation CRUD operations in SQLite."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> ObservationRepository:
        db_path = tmp_path / "obs_repo_test.db"
        db = DatabaseManager(db_path)
        db.initialize()
        return ObservationRepository(db)

    def test_create_and_get_by_id(self, repo: ObservationRepository) -> None:
        """Verify inserting an observation assigns an ID and can be retrieved."""
        obs = FarmObservation(
            crop="Coffee",
            notes="Observed small orange rust spots on lower leaves.",
            growth_stage=CropGrowthStage.VEGETATIVE,
            location_name="Jimma Sector 2",
            latitude=7.67,
            longitude=36.83,
            observer_role="Extension Agent",
        )
        stored = repo.create(obs)

        assert stored.id is not None
        assert stored.id > 0
        assert stored.crop == "Coffee"
        assert stored.growth_stage == CropGrowthStage.VEGETATIVE

        retrieved = repo.get_by_id(stored.id)
        assert retrieved is not None
        assert retrieved.id == stored.id
        assert retrieved.crop == "Coffee"
        assert retrieved.location_name == "Jimma Sector 2"
        assert retrieved.latitude == 7.67
        assert retrieved.longitude == 36.83

    def test_get_by_id_missing_returns_none(self, repo: ObservationRepository) -> None:
        """Verify querying non-existent ID returns None."""
        assert repo.get_by_id(9999) is None

    def test_list_and_filter_observations(self, repo: ObservationRepository) -> None:
        """Verify filtering by crop and ordering newest first."""
        repo.create(FarmObservation(crop="Maize", notes="Observation note 1"))
        repo.create(FarmObservation(crop="Teff", notes="Observation note 2"))
        repo.create(FarmObservation(crop="Maize", notes="Observation note 3"))

        all_records = repo.list_observations()
        assert len(all_records) == 3

        maize_records = repo.list_observations(crop="maize")
        assert len(maize_records) == 2
        assert all(r.crop.lower() == "maize" for r in maize_records)

        teff_records = repo.list_observations(crop="teff")
        assert len(teff_records) == 1
        assert teff_records[0].crop == "Teff"

    def test_count_observations(self, repo: ObservationRepository) -> None:
        """Verify count_observations returns correct totals."""
        assert repo.count_observations() == 0

        repo.create(FarmObservation(crop="Wheat", notes="Rust spots"))
        repo.create(FarmObservation(crop="Wheat", notes="Lodging after rain"))
        repo.create(FarmObservation(crop="Sorghum", notes="Healthy vegetative state"))

        assert repo.count_observations() == 3
        assert repo.count_observations(crop="wheat") == 2
        assert repo.count_observations(crop="sorghum") == 1
        assert repo.count_observations(crop="coffee") == 0

    def test_sql_injection_safety_with_special_characters(self, repo: ObservationRepository) -> None:
        """Verify parameterized queries handle quotes, semicolons, and special characters safely."""
        malicious_note = "'); DROP TABLE farm_observations; --"
        malicious_crop = "Wheat' OR '1'='1"

        obs = FarmObservation(crop=malicious_crop, notes=malicious_note)
        stored = repo.create(obs)

        retrieved = repo.get_by_id(stored.id)
        assert retrieved is not None
        assert retrieved.crop == malicious_crop
        assert retrieved.notes == malicious_note

        # Verify table was not dropped
        assert repo.count_observations() == 1
