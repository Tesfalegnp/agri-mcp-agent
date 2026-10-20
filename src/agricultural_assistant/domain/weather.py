"""Domain models for agricultural weather requests and coordinate contracts."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WeatherForecastRequest(BaseModel):
    """Data contract representing a geographic weather forecast inquiry.

    This model serves as the validated input contract for future MCP tools
    such as `get_weather_forecast`.
    """

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Geographic latitude in decimal degrees (-90.0 to +90.0).",
        examples=[7.05, 9.02, 11.59],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Geographic longitude in decimal degrees (-180.0 to +180.0).",
        examples=[38.47, 38.74, 37.39],
    )
    forecast_days: int = Field(
        default=3,
        ge=1,
        le=14,
        description="Number of forecast days requested (between 1 and 14 days).",
    )
    crop_context: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional crop type to contextualize weather risks (e.g. 'teff', 'maize').",
    )

    @field_validator("crop_context", mode="before")
    @classmethod
    def strip_crop_context(cls, value: object) -> object:
        """Strip whitespace and reject blank-only strings."""
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value
