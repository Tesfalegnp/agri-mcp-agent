"""Unit tests for the agricultural crop knowledge and disease search service."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agricultural_assistant.data.crop_knowledge import DIAGNOSTIC_DISCLAIMER
from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery
from agricultural_assistant.services.crop_service import CropService


class TestCropService:
    """Test suite for CropService queries and result formatting."""

    @pytest.fixture
    def service(self) -> CropService:
        return CropService()

    def test_search_maize_fall_armyworm(self, service: CropService) -> None:
        """Verify matching of Fall Armyworm in maize with whorl feeding symptoms."""
        query = CropSymptomQuery(
            crop_name="Maize",
            symptoms="Ragged holes in whorl leaves with yellowish frass and caterpillars.",
            growth_stage=CropGrowthStage.VEGETATIVE,
        )
        result = service.search_disease(query)

        assert result["status"] == "success"
        assert result["crop"] == "Maize"
        assert result["match_count"] >= 1
        top_match = result["potential_matches"][0]
        assert "Fall Armyworm" in top_match["disease_name"]
        assert top_match["relevance_score"] > 0
        assert len(top_match["management_recommendations"]) > 0
        assert DIAGNOSTIC_DISCLAIMER in result["diagnostic_disclaimer"]

    def test_search_teff_rust(self, service: CropService) -> None:
        """Verify matching of Teff Leaf Rust."""
        query = CropSymptomQuery(
            crop_name="Teff",
            symptoms="Reddish-brown pustules on leaves with yellowing foliage.",
            growth_stage=CropGrowthStage.HEADING,
        )
        result = service.search_disease(query)

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert any(
            "Teff Leaf Rust" in match["disease_name"]
            for match in result["potential_matches"]
        )

    def test_search_coffee_berry_disease(self, service: CropService) -> None:
        """Verify matching of Coffee Berry Disease."""
        query = CropSymptomQuery(
            crop_name="Coffee",
            symptoms="Dark sunken lesions on green berries turning into black mummies.",
            location_context="Jimma, high altitude",
        )
        result = service.search_disease(query)

        assert result["status"] == "success"
        assert result["match_count"] >= 1
        assert any(
            "Coffee Berry Disease" in match["disease_name"]
            for match in result["potential_matches"]
        )

    def test_search_unmatched_crop_symptoms(self, service: CropService) -> None:
        """Verify safe and helpful response when no disease record matches."""
        query = CropSymptomQuery(
            crop_name="Teff",
            symptoms="Mysterious blue geometric spots appearing on roots underwater.",
        )
        result = service.search_disease(query)

        assert result["status"] == "success"
        assert result["match_count"] == 0
        assert result["potential_matches"] == []
        assert "No specific disease matches were found" in result["message"]
        assert DIAGNOSTIC_DISCLAIMER in result["diagnostic_disclaimer"]

    def test_disclaimer_preserves_non_definitive_advisory(self, service: CropService) -> None:
        """Ensure no output claims definitive laboratory diagnosis."""
        query = CropSymptomQuery(
            crop_name="Wheat",
            symptoms="Yellow stripes of powdery rust pustules on leaves.",
        )
        result = service.search_disease(query)
        # Verify disclaimer stresses consultation
        assert "does not constitute a definitive laboratory diagnosis" in result["diagnostic_disclaimer"]
        assert "extension officer" in result["diagnostic_disclaimer"].lower()

    def test_no_hazardous_dosages_in_recommendations(self, service: CropService) -> None:
        """Ensure recommendations focus on IPM / cultural practices without hazardous chemical recipes."""
        for record in service.database:
            for rec in record.management_practices:
                rec_lower = rec.lower()
                assert "g/l" not in rec_lower
                assert "ml/l" not in rec_lower
                assert "tablespoon" not in rec_lower
