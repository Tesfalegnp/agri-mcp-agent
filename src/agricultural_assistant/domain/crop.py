"""Domain models for crop symptom inquiries and agronomic assessments."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CropGrowthStage(str, Enum):
    """Common phenological growth stages for agricultural crops."""

    EMERGENCE = "emergence"
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    TILLERING = "tillering"
    STEM_ELONGATION = "stem_elongation"
    BOOTING = "booting"
    HEADING = "heading"
    FLOWERING = "flowering"
    GRAIN_FILLING = "grain_filling"
    MATURITY = "maturity"
    HARVEST = "harvest"


class CropSymptomQuery(BaseModel):
    """Data contract representing a farmer's crop symptom inquiry.

    This model serves as the validated input contract for future MCP tools
    such as `search_crop_disease`.
    """

    crop_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Common or local crop name (e.g., 'maize', 'teff', 'wheat', 'coffee').",
        examples=["maize", "teff", "wheat"],
    )
    symptoms: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Observed visual symptoms, leaf discoloration, wilting, or pest patterns.",
        examples=["yellowing lower leaves with rectangular brown lesions"],
    )
    growth_stage: Optional[CropGrowthStage] = Field(
        default=None,
        description="Optional phenological crop stage when symptoms were observed.",
    )
    location_context: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Optional regional or agro-ecological context (e.g. 'Hawassa, moist highlands').",
    )
    observed_date: Optional[datetime] = Field(
        default=None,
        description="Optional timestamp when the symptom was observed (defaults to UTC now if omitted).",
    )

    @field_validator("crop_name", "symptoms", "location_context", mode="before")
    @classmethod
    def strip_and_validate_non_empty(cls, value: object) -> object:
        """Strip leading/trailing whitespace and ensure string fields are not purely whitespace."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("String field cannot be empty or purely whitespace.")
            return stripped
        return value
