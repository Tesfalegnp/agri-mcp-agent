"""Unit tests for weather request domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agricultural_assistant.domain.weather import WeatherForecastRequest


class TestWeatherForecastRequest:
    """Test suite for WeatherForecastRequest model validation rules."""

    def test_valid_minimal_request(self) -> None:
        """Test instantiation with valid latitude and longitude."""
        req = WeatherForecastRequest(latitude=9.02, longitude=38.74)
        assert req.latitude == 9.02
        assert req.longitude == 38.74
        assert req.forecast_days == 3  # Default value
        assert req.crop_context is None

    def test_valid_custom_request(self) -> None:
        """Test instantiation with custom forecast_days and crop_context."""
        req = WeatherForecastRequest(
            latitude=7.05,
            longitude=38.47,
            forecast_days=7,
            crop_context="  maize  ",
        )
        assert req.latitude == 7.05
        assert req.longitude == 38.47
        assert req.forecast_days == 7
        assert req.crop_context == "maize"

    def test_boundary_coordinates(self) -> None:
        """Test valid boundary coordinates (-90, 90, -180, 180)."""
        req_min = WeatherForecastRequest(latitude=-90.0, longitude=-180.0)
        assert req_min.latitude == -90.0
        assert req_min.longitude == -180.0

        req_max = WeatherForecastRequest(latitude=90.0, longitude=180.0)
        assert req_max.latitude == 90.0
        assert req_max.longitude == 180.0

    def test_latitude_out_of_bounds_high(self) -> None:
        """Test rejection of latitude > 90.0."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(latitude=90.001, longitude=38.0)
        assert "latitude" in str(exc_info.value)

    def test_latitude_out_of_bounds_low(self) -> None:
        """Test rejection of latitude < -90.0."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(latitude=-90.001, longitude=38.0)
        assert "latitude" in str(exc_info.value)

    def test_longitude_out_of_bounds_high(self) -> None:
        """Test rejection of longitude > 180.0."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(latitude=9.0, longitude=180.001)
        assert "longitude" in str(exc_info.value)

    def test_longitude_out_of_bounds_low(self) -> None:
        """Test rejection of longitude < -180.0."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(latitude=9.0, longitude=-180.001)
        assert "longitude" in str(exc_info.value)

    def test_forecast_days_too_low(self) -> None:
        """Test rejection of forecast_days < 1."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(latitude=9.0, longitude=38.0, forecast_days=0)
        assert "forecast_days" in str(exc_info.value)

    def test_forecast_days_too_high(self) -> None:
        """Test rejection of forecast_days > 14."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(latitude=9.0, longitude=38.0, forecast_days=15)
        assert "forecast_days" in str(exc_info.value)

    def test_non_numeric_coordinates(self) -> None:
        """Test rejection of non-numeric coordinates."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherForecastRequest(
                latitude="not_a_number",  # type: ignore[arg-type]
                longitude=38.0,
            )
        assert "latitude" in str(exc_info.value)
