"""Unit tests for crop symptom inquiry domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery


class TestCropSymptomQuery:
    """Test suite for CropSymptomQuery model validation rules."""

    def test_valid_minimal_crop_query(self) -> None:
        """Test instantiation with only required fields."""
        query = CropSymptomQuery(
            crop_name="Maize",
            symptoms="Yellowing leaves with brown spots on lower canopy.",
        )
        assert query.crop_name == "Maize"
        assert query.symptoms == "Yellowing leaves with brown spots on lower canopy."
        assert query.growth_stage is None
        assert query.location_context is None
        assert query.observed_date is None

    def test_valid_full_crop_query(self) -> None:
        """Test instantiation with all optional fields provided."""
        query = CropSymptomQuery(
            crop_name="  Teff  ",
            symptoms="Lodging and rust pustules on stems.  ",
            growth_stage=CropGrowthStage.HEADING,
            location_context="Debre Zeit, clay soil",
        )
        # Verify whitespace was stripped
        assert query.crop_name == "Teff"
        assert query.symptoms == "Lodging and rust pustules on stems."
        assert query.growth_stage == CropGrowthStage.HEADING
        assert query.location_context == "Debre Zeit, clay soil"

    def test_missing_required_crop_name(self) -> None:
        """Test validation error when crop_name is omitted."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(  # type: ignore[call-arg]
                symptoms="Leaves showing severe chlorosis.",
            )
        assert "crop_name" in str(exc_info.value)

    def test_missing_required_symptoms(self) -> None:
        """Test validation error when symptoms are omitted."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(  # type: ignore[call-arg]
                crop_name="Wheat",
            )
        assert "symptoms" in str(exc_info.value)

    def test_empty_or_whitespace_crop_name(self) -> None:
        """Test rejection of empty or purely whitespace crop_name."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(
                crop_name="   ",
                symptoms="Visible white powdery spots on leaves.",
            )
        assert "crop_name" in str(exc_info.value)

    def test_crop_name_too_short(self) -> None:
        """Test rejection of crop_name shorter than 2 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(
                crop_name="M",
                symptoms="Visible white powdery spots on leaves.",
            )
        assert "crop_name" in str(exc_info.value)

    def test_crop_name_too_long(self) -> None:
        """Test rejection of crop_name exceeding 100 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(
                crop_name="A" * 101,
                symptoms="Visible white powdery spots on leaves.",
            )
        assert "crop_name" in str(exc_info.value)

    def test_symptoms_too_short(self) -> None:
        """Test rejection of symptoms shorter than 5 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(
                crop_name="Wheat",
                symptoms="Dry",
            )
        assert "symptoms" in str(exc_info.value)

    def test_symptoms_too_long(self) -> None:
        """Test rejection of symptoms exceeding 1000 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(
                crop_name="Wheat",
                symptoms="S" * 1001,
            )
        assert "symptoms" in str(exc_info.value)

    def test_invalid_growth_stage_enum(self) -> None:
        """Test rejection of invalid growth stage values."""
        with pytest.raises(ValidationError) as exc_info:
            CropSymptomQuery(
                crop_name="Sorghum",
                symptoms="Wilting leaves after dry spell.",
                growth_stage="hyper_growth",  # type: ignore[arg-type]
            )
        assert "growth_stage" in str(exc_info.value)
