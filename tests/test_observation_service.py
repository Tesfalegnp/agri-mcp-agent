"""Unit tests for ObservationService validation and business rules."""

from __future__ import annotations

from pathlib import Path
import pytest

from agricultural_assistant.services.observation_service import ObservationService
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.observation_repository import ObservationRepository


class TestObservationService:
    """Test suite for ObservationService."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> ObservationService:
        db_path = tmp_path / "obs_service_test.db"
        db = DatabaseManager(db_path)
        db.initialize()
        repo = ObservationRepository(db)
        return ObservationService(repo)

    def test_record_observation_success(self, service: ObservationService) -> None:
        """Verify valid observation payload returns success status with ID."""
        result = service.record_observation(
            crop="Teff",
            notes="Panicles emerged with no signs of head smut.",
            growth_stage="heading",
            location_name="Debre Zeit, Plot 4",
            latitude=8.75,
            longitude=38.98,
            observer_role="farmer",
        )
        assert result["status"] == "success"
        assert result["observation_id"] == 1
        assert result["crop"] == "Teff"
        assert "Debre Zeit" in result["observation"]["location_name"]

    def test_record_observation_validation_failure_short_notes(
        self, service: ObservationService
    ) -> None:
        """Verify rejection when notes are shorter than 5 characters."""
        result = service.record_observation(crop="Maize", notes="Bad")
        assert result["status"] == "error"
        assert result["error_type"] == "validation_error"
        assert "notes" in result["message"]

    def test_record_observation_invalid_growth_stage(self, service: ObservationService) -> None:
        """Verify rejection of invalid growth stage."""
        result = service.record_observation(
            crop="Maize",
            notes="Valid length note here",
            growth_stage="super_flowering",
        )
        assert result["status"] == "error"
        assert result["error_type"] == "validation_error"
        assert "Invalid growth_stage" in result["message"]

    def test_record_observation_incomplete_coordinates(self, service: ObservationService) -> None:
        """Verify rejection when latitude is given without longitude."""
        result = service.record_observation(
            crop="Wheat",
            notes="Applied top-dressing urea fertilizer.",
            latitude=9.02,
            longitude=None,
        )
        assert result["status"] == "error"
        assert result["error_type"] == "validation_error"
        assert "Both latitude and longitude" in result["message"]

    def test_get_observation(self, service: ObservationService) -> None:
        """Verify get_observation retrieves existing record or returns not_found."""
        rec = service.record_observation(crop="Sorghum", notes="Normal vegetative growth.")
        obs_id = rec["observation_id"]

        found = service.get_observation(obs_id)
        assert found["status"] == "success"
        assert found["observation"]["id"] == obs_id

        missing = service.get_observation(9999)
        assert missing["status"] == "error"
        assert missing["error_type"] == "not_found"

        invalid_id = service.get_observation(-1)
        assert invalid_id["status"] == "error"
        assert invalid_id["error_type"] == "validation_error"

    def test_list_and_count_observations(self, service: ObservationService) -> None:
        """Verify listing observations with limits and total counts."""
        service.record_observation(crop="Teff", notes="Note 1 for teff")
        service.record_observation(crop="Teff", notes="Note 2 for teff")
        service.record_observation(crop="Maize", notes="Note 1 for maize")

        all_list = service.list_observations()
        assert all_list["status"] == "success"
        assert all_list["total_count"] == 3
        assert len(all_list["observations"]) == 3

        teff_list = service.list_observations(crop="teff", limit=1)
        assert teff_list["status"] == "success"
        assert teff_list["total_count"] == 2
        assert teff_list["returned_count"] == 1

        counts = service.count_observations()
        assert counts["count"] == 3
        teff_counts = service.count_observations(crop="teff")
        assert teff_counts["count"] == 2
