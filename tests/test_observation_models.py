"""Unit tests for farm observation domain models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agricultural_assistant.domain.crop import CropGrowthStage
from agricultural_assistant.domain.observation import FarmObservation


class TestFarmObservation:
    """Test suite for FarmObservation model validation rules."""

    def test_valid_minimal_observation(self) -> None:
        """Test observation creation with only required fields."""
        obs = FarmObservation(
            crop="Coffee",
            notes="Observed small orange rust spots on underside of leaves.",
        )
        assert obs.crop == "Coffee"
        assert obs.notes == "Observed small orange rust spots on underside of leaves."
        assert obs.growth_stage is None
        assert obs.location_name is None
        assert obs.latitude is None
        assert obs.longitude is None
        assert obs.observer_role is None
        # Observed_at defaults to current UTC time
        assert isinstance(obs.observed_at, datetime)
        assert obs.observed_at.tzinfo is not None

    def test_valid_full_observation(self) -> None:
        """Test observation creation with all fields populated."""
        now = datetime.now(timezone.utc)
        obs = FarmObservation(
            crop="  Maize  ",
            notes="Fall armyworm damage visible on whorl leaves.  ",
            growth_stage=CropGrowthStage.VEGETATIVE,
            observed_at=now,
            location_name="East Sector, Plot 4",
            latitude=7.05,
            longitude=38.47,
            observer_role="Extension Agent",
        )
        assert obs.crop == "Maize"
        assert obs.notes == "Fall armyworm damage visible on whorl leaves."
        assert obs.growth_stage == CropGrowthStage.VEGETATIVE
        assert obs.observed_at == now
        assert obs.location_name == "East Sector, Plot 4"
        assert obs.latitude == 7.05
        assert obs.longitude == 38.47
        assert obs.observer_role == "Extension Agent"

    def test_missing_required_crop(self) -> None:
        """Test rejection when crop is omitted."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(  # type: ignore[call-arg]
                notes="Heavy rain caused slight waterlogging.",
            )
        assert "crop" in str(exc_info.value)

    def test_missing_required_notes(self) -> None:
        """Test rejection when notes are omitted."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(  # type: ignore[call-arg]
                crop="Teff",
            )
        assert "notes" in str(exc_info.value)

    def test_notes_too_short(self) -> None:
        """Test rejection of notes shorter than 5 characters."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(
                crop="Teff",
                notes="Bad",
            )
        assert "notes" in str(exc_info.value)

    def test_notes_too_long(self) -> None:
        """Test rejection of notes exceeding 2000 characters."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(
                crop="Teff",
                notes="N" * 2001,
            )
        assert "notes" in str(exc_info.value)

    def test_incomplete_coordinates_latitude_only(self) -> None:
        """Test rejection when latitude is provided without longitude."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(
                crop="Wheat",
                notes="Applied top-dressing urea fertilizer.",
                latitude=9.02,
                longitude=None,
            )
        assert "Both latitude and longitude must be provided together" in str(exc_info.value)

    def test_incomplete_coordinates_longitude_only(self) -> None:
        """Test rejection when longitude is provided without latitude."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(
                crop="Wheat",
                notes="Applied top-dressing urea fertilizer.",
                latitude=None,
                longitude=38.74,
            )
        assert "Both latitude and longitude must be provided together" in str(exc_info.value)

    def test_coordinates_out_of_bounds(self) -> None:
        """Test rejection of out-of-range coordinates."""
        with pytest.raises(ValidationError) as exc_info:
            FarmObservation(
                crop="Wheat",
                notes="Applied top-dressing urea fertilizer.",
                latitude=95.0,
                longitude=38.74,
            )
        assert "latitude" in str(exc_info.value)
