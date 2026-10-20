"""Domain models for recording structured farm observations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from agricultural_assistant.domain.crop import CropGrowthStage


class FarmObservation(BaseModel):
    """Data contract representing a recorded farm observation or field note.

    This model serves as the validated input contract for future MCP tools
    such as `record_farm_observation`.
    """

    crop: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Name of the crop observed (e.g. 'maize', 'coffee', 'teff').",
    )
    notes: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Detailed observation notes, symptoms, pest sightings, or management actions.",
    )
    growth_stage: Optional[CropGrowthStage] = Field(
        default=None,
        description="Optional phenological growth stage at the time of observation.",
    )
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of observation in UTC.",
    )
    location_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Descriptive location or field identifier (e.g. 'North Field, Plot 3B').",
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Optional geographic latitude in decimal degrees (-90.0 to +90.0).",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Optional geographic longitude in decimal degrees (-180.0 to +180.0).",
    )
    observer_role: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional designation of person recording the note (e.g., 'farmer', 'agronomist').",
    )

    @field_validator("crop", "notes", "location_name", "observer_role", mode="before")
    @classmethod
    def strip_and_validate_strings(cls, value: object) -> object:
        """Strip whitespace from strings and ensure required strings are not purely whitespace."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("String field cannot be empty or purely whitespace.")
            return stripped
        return value

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> FarmObservation:
        """Ensure latitude and longitude are either both provided or both omitted."""
        has_lat = self.latitude is not None
        has_lon = self.longitude is not None
        if has_lat != has_lon:
            raise ValueError(
                "Both latitude and longitude must be provided together if coordinates are specified."
            )
        return self


class StoredFarmObservation(FarmObservation):
    """Data contract representing a farm observation persisted in SQLite."""

    id: int = Field(..., description="Unique database identifier for the observation.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when record was committed to the database.",
    )
