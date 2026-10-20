"""Unit tests for the WeatherService using deterministic mocked HTTP responses."""

from __future__ import annotations

import httpx
import pytest

from agricultural_assistant.domain.weather import WeatherForecastRequest
from agricultural_assistant.services.weather_service import (
    OPEN_METEO_ATTRIBUTION,
    WeatherService,
)


class TestWeatherService:
    """Test suite for WeatherService with mocked Open-Meteo responses."""

    @pytest.mark.anyio
    async def test_successful_mocked_forecast(self) -> None:
        """Verify parsing of valid Open-Meteo JSON response."""
        mock_payload = {
            "latitude": 9.02,
            "longitude": 38.74,
            "elevation": 2355.0,
            "timezone": "Africa/Addis_Ababa",
            "daily_units": {
                "time": "iso8601",
                "temperature_2m_max": "°C",
                "temperature_2m_min": "°C",
                "precipitation_sum": "mm",
                "precipitation_probability_max": "%",
            },
            "daily": {
                "time": ["2026-10-20", "2026-10-21"],
                "temperature_2m_max": [22.5, 23.0],
                "temperature_2m_min": [9.4, 8.8],
                "precipitation_sum": [0.0, 1.2],
                "precipitation_probability_max": [5, 45],
            },
        }

        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_payload)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            service = WeatherService(client=client)
            req = WeatherForecastRequest(
                latitude=9.02, longitude=38.74, forecast_days=2, crop_context="teff"
            )
            result = await service.get_forecast(req)

        assert result["status"] == "success"
        assert result["provider"] == "Open-Meteo"
        assert result["attribution"] == OPEN_METEO_ATTRIBUTION
        assert result["crop_context"] == "teff"
        assert result["forecast_days"] == 2
        assert len(result["daily_forecast"]) == 2

        day1 = result["daily_forecast"][0]
        assert day1["date"] == "2026-10-20"
        assert day1["max_temperature_c"] == 22.5
        assert day1["min_temperature_c"] == 9.4
        assert day1["precipitation_mm"] == 0.0
        assert day1["precipitation_probability_pct"] == 5

    @pytest.mark.anyio
    async def test_timeout_handling(self) -> None:
        """Verify graceful error reporting when external request times out."""
        def raise_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Connection timed out", request=request)

        transport = httpx.MockTransport(raise_timeout)
        async with httpx.AsyncClient(transport=transport) as client:
            service = WeatherService(client=client)
            req = WeatherForecastRequest(latitude=7.05, longitude=38.47)
            result = await service.get_forecast(req)

        assert result["status"] == "error"
        assert result["error_type"] == "timeout"
        assert "timeout" in result["message"].lower()

    @pytest.mark.anyio
    async def test_network_connection_error(self) -> None:
        """Verify network connection failures return safe error responses."""
        def raise_connect_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Failed to resolve host", request=request)

        transport = httpx.MockTransport(raise_connect_error)
        async with httpx.AsyncClient(transport=transport) as client:
            service = WeatherService(client=client)
            req = WeatherForecastRequest(latitude=7.05, longitude=38.47)
            result = await service.get_forecast(req)

        assert result["status"] == "error"
        assert result["error_type"] == "network_error"
        assert "unable to connect" in result["message"].lower()

    @pytest.mark.anyio
    async def test_http_status_error(self) -> None:
        """Verify HTTP 500 error from provider produces clean structured error."""
        transport = httpx.MockTransport(
            lambda request: httpx.Response(500, text="Internal Server Error")
        )
        async with httpx.AsyncClient(transport=transport) as client:
            service = WeatherService(client=client)
            req = WeatherForecastRequest(latitude=9.02, longitude=38.74)
            result = await service.get_forecast(req)

        assert result["status"] == "error"
        assert result["error_type"] == "http_error"
        assert result["status_code"] == 500

    @pytest.mark.anyio
    async def test_malformed_json_response(self) -> None:
        """Verify handling of invalid non-JSON payload from provider."""
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>Gateway Error</html>", headers={"Content-Type": "text/html"})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            service = WeatherService(client=client)
            req = WeatherForecastRequest(latitude=9.02, longitude=38.74)
            result = await service.get_forecast(req)

        assert result["status"] == "error"
        assert result["error_type"] == "invalid_json"

    @pytest.mark.anyio
    async def test_missing_daily_payload(self) -> None:
        """Verify handling of JSON payload lacking 'daily' dictionary."""
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"latitude": 9.02, "longitude": 38.74})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            service = WeatherService(client=client)
            req = WeatherForecastRequest(latitude=9.02, longitude=38.74)
            result = await service.get_forecast(req)

        assert result["status"] == "error"
        assert result["error_type"] == "missing_data"
