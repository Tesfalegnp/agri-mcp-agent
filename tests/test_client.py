"""Unit and integration tests for the Agricultural MCP Client."""

from __future__ import annotations

import io
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent, Tool

from agricultural_assistant.client.cli import (
    format_crop_result,
    format_weather_result,
)
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient


class TestAgriculturalMCPClient:
    """Test suite for AgriculturalMCPClient."""

    @pytest.mark.anyio
    async def test_client_not_connected_raises(self) -> None:
        """Calling session when not connected raises ConnectionError."""
        client = AgriculturalMCPClient(server_command="dummy_nonexistent")
        with pytest.raises(ConnectionError, match="not connected"):
            _ = client.session

    @pytest.mark.anyio
    async def test_invalid_server_binary_raises_connection_error(self) -> None:
        """Attempting to connect to non-existent executable raises ConnectionError."""
        client = AgriculturalMCPClient(server_command="__non_existent_binary__12345")
        with pytest.raises(ConnectionError):
            await client.connect()

    @pytest.mark.anyio
    async def test_mock_session_tool_calls(self) -> None:
        """Verify client methods route to session.call_tool with correct parameters."""
        client = AgriculturalMCPClient()

        # Mock the session
        mock_session = AsyncMock()
        mock_tool = Tool(
            name="search_crop_disease",
            description="Mock crop tool",
            input_schema={"properties": {"crop_name": {"type": "string"}}},
        )
        mock_session.list_tools.return_value = MagicMock(tools=[mock_tool])

        mock_crop_response = MagicMock()
        mock_crop_response.is_error = False
        mock_crop_response.content = [
            TextContent(type="text", text='{"status": "success", "crop": "maize", "match_count": 1}')
        ]
        mock_session.call_tool.return_value = mock_crop_response

        client._session = mock_session

        # Test list_tools
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "search_crop_disease"

        # Test search_crop_disease
        res = await client.search_crop_disease(
            crop_name="maize",
            symptoms="yellow leaves",
            growth_stage="vegetative",
            location_context="Hawassa",
        )
        assert res["status"] == "success"
        assert res["crop"] == "maize"
        mock_session.call_tool.assert_called_once_with(
            "search_crop_disease",
            {
                "crop_name": "maize",
                "symptoms": "yellow leaves",
                "growth_stage": "vegetative",
                "location_context": "Hawassa",
                "language": "en",
            },
        )

    @pytest.mark.anyio
    async def test_mock_weather_call(self) -> None:
        """Verify weather forecast method formatting and deserialization."""
        client = AgriculturalMCPClient()
        mock_session = AsyncMock()

        mock_weather_response = MagicMock()
        mock_weather_response.is_error = False
        mock_weather_response.content = [
            TextContent(
                type="text",
                text='{"status": "success", "provider": "Open-Meteo", "forecast_days": 2, "daily_forecast": []}',
            )
        ]
        mock_session.call_tool.return_value = mock_weather_response
        client._session = mock_session

        res = await client.get_weather_forecast(
            latitude=9.02, longitude=38.74, forecast_days=2, crop_context="teff"
        )
        assert res["status"] == "success"
        assert res["provider"] == "Open-Meteo"
        mock_session.call_tool.assert_called_once_with(
            "get_weather_forecast",
            {
                "latitude": 9.02,
                "longitude": 38.74,
                "forecast_days": 2,
                "crop_context": "teff",
            },
        )

    @pytest.mark.anyio
    async def test_mcp_tool_error_handling(self) -> None:
        """Verify client converts tool is_error to structured error."""
        client = AgriculturalMCPClient()
        mock_session = AsyncMock()

        mock_err_response = MagicMock()
        mock_err_response.is_error = True
        mock_err_response.content = [TextContent(type="text", text="Internal server error")]
        mock_session.call_tool.return_value = mock_err_response
        client._session = mock_session

        res = await client.search_crop_disease("maize", "symptoms")
        assert res["status"] == "error"
        assert res["error_type"] == "mcp_tool_error"

    @pytest.mark.anyio
    async def test_mock_observation_calls(self) -> None:
        """Verify client helpers for observation tools serialize and invoke correctly."""
        client = AgriculturalMCPClient()
        mock_session = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.is_error = False
        mock_resp.content = [TextContent(type="text", text='{"status": "success", "observation_id": 5}')]
        mock_session.call_tool.return_value = mock_resp
        client._session = mock_session

        rec_res = await client.record_farm_observation("Teff", "Stems falling", growth_stage="heading")
        assert rec_res["status"] == "success"
        assert rec_res["observation_id"] == 5

        mock_resp.content = [TextContent(type="text", text='{"status": "success", "count": 10}')]
        count_res = await client.count_farm_observations(crop="Teff")
        assert count_res["count"] == 10

        mock_resp.content = [TextContent(type="text", text='{"status": "success", "total_observations": 10}')]
        sum_res = await client.summarize_farm_observations(crop="Teff")
        assert sum_res["total_observations"] == 10

        mock_resp.content = [TextContent(type="text", text='{"status": "success", "cumulative_gdd": 150.0}')]
        gdd_res = await client.calculate_agronomic_metrics(daily_weather=[{"max_temp_c": 25.0, "min_temp_c": 15.0}])
        assert gdd_res["cumulative_gdd"] == 150.0


class TestCLIFormatters:
    """Test suite for CLI result formatting helpers."""

    def test_format_crop_result_success(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_crop_result prints structured diagnostic information."""
        result: Dict[str, Any] = {
            "status": "success",
            "crop": "teff",
            "message": "Found 1 potential match.",
            "diagnostic_disclaimer": "Advisory only.",
            "potential_matches": [
                {
                    "disease_name": "Teff Rust",
                    "scientific_name": "Uromyces eragrostidis",
                    "relevance_score": 6,
                    "common_symptoms": ["orange pustules"],
                    "management_recommendations": ["Plant resistant varieties."],
                    "source_reference": "EIAR bulletin",
                }
            ],
        }
        format_crop_result(result)
        captured = capsys.readouterr().out
        assert "Teff Rust" in captured
        assert "Uromyces eragrostidis" in captured
        assert "Plant resistant varieties." in captured
        assert "Advisory only." in captured

    def test_format_crop_result_error(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_crop_result prints error message gracefully."""
        result = {"status": "error", "message": "Failed validation."}
        format_crop_result(result)
        captured = capsys.readouterr().out
        assert "[Error] Failed validation." in captured

    def test_format_weather_result_success(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_weather_result prints table with temperatures and precipitation."""
        result: Dict[str, Any] = {
            "status": "success",
            "provider": "Open-Meteo",
            "attribution": "CC BY 4.0",
            "coordinates": {"latitude": 9.02, "longitude": 38.74},
            "units": {"temperature": "°C", "precipitation": "mm", "precipitation_probability": "%"},
            "daily_forecast": [
                {
                    "date": "2026-10-21",
                    "max_temperature_c": 22.5,
                    "min_temperature_c": 9.4,
                    "precipitation_mm": 0.0,
                    "precipitation_probability_pct": 5,
                }
            ],
        }
        format_weather_result(result)
        captured = capsys.readouterr().out
        assert "2026-10-21" in captured
        assert "22.5°C" in captured
        assert "9.4°C" in captured
        assert "Open-Meteo" in captured

    def test_format_observation_detail(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_observation_detail prints observation metadata."""
        from agricultural_assistant.client.cli import format_observation_detail

        obs = {
            "id": 12,
            "crop": "Coffee",
            "growth_stage": "flowering",
            "observed_at": "2026-10-20T10:00:00Z",
            "location_name": "Jimma plot 3",
            "latitude": 7.67,
            "longitude": 36.83,
            "observer_role": "agronomist",
            "created_at": "2026-10-20T10:05:00Z",
            "notes": "Observed early CBD symptoms.",
        }
        format_observation_detail(obs)
        captured = capsys.readouterr().out
        assert "Observation ID: #12" in captured
        assert "Coffee" in captured
        assert "flowering" in captured
        assert "Jimma plot 3" in captured
        assert "Observed early CBD symptoms." in captured

    def test_format_observation_list(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_observation_list formats tabular view."""
        from agricultural_assistant.client.cli import format_observation_list

        list_res = {
            "status": "success",
            "total_count": 2,
            "returned_count": 2,
            "observations": [
                {"id": 1, "crop": "Teff", "growth_stage": "heading", "observed_at": "2026-10-18T10:00:00Z", "location_name": "Debre Zeit"},
                {"id": 2, "crop": "Maize", "growth_stage": "vegetative", "observed_at": "2026-10-19T10:00:00Z", "location_name": "Hawassa"},
            ],
        }
        format_observation_list(list_res)
        captured = capsys.readouterr().out
        assert "#1" in captured
        assert "Teff" in captured
        assert "#2" in captured
        assert "Maize" in captured

    def test_format_observation_summary(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_observation_summary prints aggregation metrics."""
        from agricultural_assistant.client.cli import format_observation_summary

        summary_res = {
            "status": "success",
            "total_observations": 4,
            "date_range": {"earliest_observed": "2026-05-01", "latest_observed": "2026-06-01"},
            "crop_distribution": {"Maize": 3, "Teff": 1},
            "growth_stage_distribution": {"vegetative": 3, "heading": 1},
            "recorded_symptom_mentions": {"armyworm": 2},
            "confidence_note": "Sample size note.",
        }
        format_observation_summary(summary_res)
        captured = capsys.readouterr().out
        assert "Total Observations: 4" in captured
        assert "Maize" in captured
        assert "armyworm" in captured

    def test_format_agronomic_metrics(self, capsys: pytest.CaptureFixture) -> None:
        """Verify format_agronomic_metrics displays GDD and precipitation."""
        from agricultural_assistant.client.cli import format_agronomic_metrics

        metrics_res = {
            "growing_degree_days": {
                "cumulative_gdd": 34.5,
                "base_temperature_c": 10.0,
                "daily_gdd": [{"date": "Day 1", "max_temp_c": 26.0, "min_temp_c": 12.0, "daily_gdd": 9.0}],
            },
            "precipitation_summary": {
                "cumulative_precipitation_mm": 18.2,
                "rainy_days_count": 2,
                "longest_consecutive_dry_days": 2,
            },
            "disclaimer": "Calculation disclaimer.",
        }
        format_agronomic_metrics(metrics_res)
        captured = capsys.readouterr().out
        assert "34.5 heat units" in captured
        assert "18.2 mm" in captured
        assert "Calculation disclaimer." in captured
