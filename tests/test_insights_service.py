"""Unit tests for FarmInsightsService and AgronomicCalculator."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from agricultural_assistant.domain.crop import CropGrowthStage
from agricultural_assistant.domain.observation import FarmObservation
from agricultural_assistant.services.insights_service import (
    AgronomicCalculator,
    FarmInsightsService,
)
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.observation_repository import ObservationRepository


class TestFarmInsightsService:
    """Test suite for FarmInsightsService aggregation logic."""

    @pytest.fixture
    def insights_service(self, tmp_path: Path) -> FarmInsightsService:
        db_path = tmp_path / "insights_test.db"
        db = DatabaseManager(db_path)
        db.initialize()
        repo = ObservationRepository(db)
        return FarmInsightsService(repo)

    def test_empty_observations_summary(self, insights_service: FarmInsightsService) -> None:
        """Verify summary on empty database returns structured zero-state."""
        summary = insights_service.summarize_observations()
        assert summary["status"] == "success"
        assert summary["total_observations"] == 0
        assert summary["date_range"] is None
        assert "zero records" in summary["confidence_note"].lower()

    def test_populated_observations_summary(self, insights_service: FarmInsightsService) -> None:
        """Verify metric distributions and keyword extraction with populated records."""
        repo = insights_service.repository
        repo.create(
            FarmObservation(
                crop="Maize",
                notes="Heavy fall armyworm caterpillar damage observed in whorl.",
                growth_stage=CropGrowthStage.VEGETATIVE,
                observed_at=datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc),
            )
        )
        repo.create(
            FarmObservation(
                crop="Maize",
                notes="Yellowing lower leaves with gray leaf spot lesions.",
                growth_stage=CropGrowthStage.FLOWERING,
                observed_at=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            )
        )
        repo.create(
            FarmObservation(
                crop="Teff",
                notes="Orange rust pustules spreading across field canopy.",
                growth_stage=CropGrowthStage.HEADING,
                observed_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
            )
        )
        repo.create(
            FarmObservation(
                crop="Teff",
                notes="Healthy crop with minimal lodging after rains.",
                growth_stage=CropGrowthStage.GRAIN_FILLING,
                observed_at=datetime(2026, 6, 15, 11, 0, tzinfo=timezone.utc),
            )
        )
        repo.create(
            FarmObservation(
                crop="Coffee",
                notes="Coffee berry disease lesions on green berries.",
                growth_stage=CropGrowthStage.GRAIN_FILLING,
                observed_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            )
        )

        summary = insights_service.summarize_observations()
        assert summary["status"] == "success"
        assert summary["total_observations"] == 5
        assert summary["crop_distribution"]["Maize"] == 2
        assert summary["crop_distribution"]["Teff"] == 2
        assert summary["crop_distribution"]["Coffee"] == 1
        assert summary["growth_stage_distribution"]["vegetative"] == 1
        assert summary["growth_stage_distribution"]["flowering"] == 1

        # Check date range
        assert summary["date_range"]["earliest_observed"] == "2026-05-10T08:00:00+00:00"
        assert summary["date_range"]["latest_observed"] == "2026-07-01T12:00:00+00:00"

        # Check keyword scanning
        mentions = summary["recorded_symptom_mentions"]
        assert mentions.get("armyworm") == 1
        assert mentions.get("rust") == 1
        assert mentions.get("lodging") == 1

    def test_filter_by_crop_summary(self, insights_service: FarmInsightsService) -> None:
        """Verify summary properly restricts metrics when filtering by crop."""
        repo = insights_service.repository
        repo.create(FarmObservation(crop="Wheat", notes="Yellow rust observed on leaves."))
        repo.create(FarmObservation(crop="Maize", notes="Stem borer sightings."))

        wheat_summary = insights_service.summarize_observations(crop="wheat")
        assert wheat_summary["total_observations"] == 1
        assert "Wheat" in wheat_summary["crop_distribution"]
        assert "Maize" not in wheat_summary["crop_distribution"]


class TestAgronomicCalculator:
    """Test suite for mathematical and agronomic calculations."""

    def test_hand_calculated_growing_degree_days(self) -> None:
        """Verify GDD calculations against exact hand-calculated expected values."""
        # Baseline = 10°C, Upper Cutoff = 30°C
        weather_data = [
            {"date": "2026-10-01", "max_temp_c": 24.0, "min_temp_c": 12.0},  # Mean = 18°C, GDD = 8.0
            {"date": "2026-10-02", "max_temp_c": 34.0, "min_temp_c": 14.0},  # Capped at 30°C, Mean = 22°C, GDD = 12.0
            {"date": "2026-10-03", "max_temp_c": 8.0, "min_temp_c": 2.0},    # Below base (adj min 10), Mean = 9°C, GDD = 0.0
        ]

        result = AgronomicCalculator.calculate_growing_degree_days(
            daily_temperatures=weather_data,
            base_temperature_c=10.0,
            upper_cutoff_c=30.0,
        )

        assert result["status"] == "success"
        assert result["total_days_evaluated"] == 3
        assert result["daily_gdd"][0]["daily_gdd"] == 8.0
        assert result["daily_gdd"][1]["daily_gdd"] == 12.0
        assert result["daily_gdd"][2]["daily_gdd"] == 0.0
        assert result["cumulative_gdd"] == 20.0

    def test_hand_calculated_precipitation_summary(self) -> None:
        """Verify cumulative rainfall and dry streak calculations."""
        rainfall_data = [
            {"date": "2026-10-01", "precipitation_mm": 0.0},
            {"date": "2026-10-02", "precipitation_mm": 5.5},
            {"date": "2026-10-03", "precipitation_mm": 12.0},
            {"date": "2026-10-04", "precipitation_mm": 0.2},
            {"date": "2026-10-05", "precipitation_mm": 0.0},
        ]

        result = AgronomicCalculator.calculate_precipitation_summary(
            daily_rainfall=rainfall_data,
            dry_day_threshold_mm=1.0,
        )

        assert result["status"] == "success"
        assert result["total_days"] == 5
        assert result["cumulative_precipitation_mm"] == 17.7
        assert result["rainy_days_count"] == 2
        assert result["dry_days_count"] == 3
        assert result["longest_consecutive_dry_days"] == 2

    def test_empty_calculator_inputs(self) -> None:
        """Verify error status when inputs are empty."""
        res_gdd = AgronomicCalculator.calculate_growing_degree_days([], 10.0)
        assert res_gdd["status"] == "error"

        res_precip = AgronomicCalculator.calculate_precipitation_summary([])
        assert res_precip["status"] == "error"
