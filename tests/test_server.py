"""Unit and integration tests for the Agricultural MCP Server."""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from agricultural_assistant.domain.weather import WeatherForecastRequest
from agricultural_assistant.server.app import create_server
from agricultural_assistant.services.crop_service import CropService
from agricultural_assistant.services.weather_service import WeatherService


class MockWeatherService(WeatherService):
    """Mock WeatherService returning deterministic responses without network calls."""

    def __init__(self, should_fail: bool = False) -> None:
        super().__init__()
        self.should_fail = should_fail

    async def get_forecast(self, request: WeatherForecastRequest) -> Dict[str, Any]:
        if self.should_fail:
            return {
                "status": "error",
                "error_type": "timeout",
                "message": "Simulated weather service timeout.",
                "coordinates": {"latitude": request.latitude, "longitude": request.longitude},
            }
        return {
            "status": "success",
            "provider": "Open-Meteo",
            "coordinates": {"latitude": request.latitude, "longitude": request.longitude},
            "forecast_days": request.forecast_days,
            "daily_forecast": [
                {
                    "date": "2026-10-20",
                    "max_temperature_c": 22.0,
                    "min_temperature_c": 10.0,
                    "precipitation_mm": 0.0,
                    "precipitation_probability_pct": 10,
                }
            ],
        }


class TestMCPServer:
    """Test suite for Agricultural MCP Server tools and validation."""

    @pytest.fixture
    def server(self):
        return create_server(
            crop_service=CropService(),
            weather_service=MockWeatherService(),
        )

    @pytest.mark.anyio
    async def test_server_initialization_and_tool_discovery(self, server) -> None:
        """Verify server registers both tools with accurate descriptions and schemas."""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]

        assert "search_crop_disease" in tool_names
        assert "get_weather_forecast" in tool_names

        # Check search_crop_disease tool schema
        crop_tool = next(t for t in tools if t.name == "search_crop_disease")
        assert "crop" in crop_tool.description.lower()
        properties = crop_tool.input_schema.get("properties", {})
        assert "crop_name" in properties
        assert "symptoms" in properties

        # Check get_weather_forecast tool schema
        weather_tool = next(t for t in tools if t.name == "get_weather_forecast")
        assert "weather" in weather_tool.description.lower()
        w_properties = weather_tool.input_schema.get("properties", {})
        assert "latitude" in w_properties
        assert "longitude" in w_properties

    @pytest.mark.anyio
    async def test_search_crop_disease_execution(self, server) -> None:
        """Verify executing search_crop_disease returns valid structured content."""
        result = await server.call_tool(
            "search_crop_disease",
            {
                "crop_name": "maize",
                "symptoms": "ragged leaf holes and yellowish frass in whorl",
                "growth_stage": "vegetative",
            },
        )
        assert not result.is_error
        assert len(result.content) > 0
        text_content = result.content[0].text
        data = json.loads(text_content)
        assert data["status"] == "success"
        assert data["crop"] == "maize"
        assert data["match_count"] >= 1

    @pytest.mark.anyio
    async def test_search_crop_disease_validation_failure(self, server) -> None:
        """Verify validation errors are caught and returned as structured error responses."""
        # crop_name too short, symptoms too short
        result = await server.call_tool(
            "search_crop_disease",
            {
                "crop_name": "m",
                "symptoms": "bad",
            },
        )
        assert not result.is_error  # Clean protocol response
        text_content = result.content[0].text
        data = json.loads(text_content)
        assert data["status"] == "error"
        assert data["error_type"] == "validation_error"
        assert "validation failed" in data["message"].lower()

    @pytest.mark.anyio
    async def test_search_crop_disease_invalid_growth_stage(self, server) -> None:
        """Verify invalid growth stage returns validation error."""
        result = await server.call_tool(
            "search_crop_disease",
            {
                "crop_name": "wheat",
                "symptoms": "yellow leaf rust stripes on leaves",
                "growth_stage": "alien_growth_phase",
            },
        )
        text_content = result.content[0].text
        data = json.loads(text_content)
        assert data["status"] == "error"
        assert "Invalid growth_stage" in data["message"]

    @pytest.mark.anyio
    async def test_get_weather_forecast_execution(self, server) -> None:
        """Verify executing get_weather_forecast returns valid structured weather data."""
        result = await server.call_tool(
            "get_weather_forecast",
            {
                "latitude": 9.02,
                "longitude": 38.74,
                "forecast_days": 1,
            },
        )
        assert not result.is_error
        text_content = result.content[0].text
        data = json.loads(text_content)
        assert data["status"] == "success"
        assert data["provider"] == "Open-Meteo"
        assert len(data["daily_forecast"]) == 1

    @pytest.mark.anyio
    async def test_get_weather_forecast_invalid_coordinates(self, server) -> None:
        """Verify out-of-bounds coordinates return structured validation error."""
        result = await server.call_tool(
            "get_weather_forecast",
            {
                "latitude": 95.0,  # Invalid (>90.0)
                "longitude": 38.74,
            },
        )
        text_content = result.content[0].text
        data = json.loads(text_content)
        assert data["status"] == "error"
        assert data["error_type"] == "validation_error"

    @pytest.mark.anyio
    async def test_weather_service_failure_handling(self) -> None:
        """Verify weather failure returns error dictionary without server crash."""
        failing_server = create_server(
            crop_service=CropService(),
            weather_service=MockWeatherService(should_fail=True),
        )
        result = await failing_server.call_tool(
            "get_weather_forecast",
            {
                "latitude": 9.02,
                "longitude": 38.74,
            },
        )
        text_content = result.content[0].text
        data = json.loads(text_content)
        assert data["status"] == "error"
        assert data["error_type"] == "timeout"
