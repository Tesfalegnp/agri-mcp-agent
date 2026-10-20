"""Integration tests for MCP historical insights and calculation tools."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from agricultural_assistant.server.app import create_server
from agricultural_assistant.services.insights_service import FarmInsightsService
from agricultural_assistant.services.observation_service import ObservationService
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.observation_repository import ObservationRepository


class TestInsightsTools:
    """Test suite for MCP insight tools."""

    @pytest.fixture
    def server(self, tmp_path: Path):
        db_path = tmp_path / "insights_tools_test.db"
        db = DatabaseManager(db_path)
        db.initialize()
        repo = ObservationRepository(db)
        obs_service = ObservationService(repo)
        insights_service = FarmInsightsService(repo)
        return create_server(
            observation_service=obs_service,
            insights_service=insights_service,
        )

    @pytest.mark.anyio
    async def test_tool_discovery_includes_insights_tools(self, server) -> None:
        """Verify server registers summarize_farm_observations and calculate_agronomic_metrics."""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]

        assert "summarize_farm_observations" in tool_names
        assert "calculate_agronomic_metrics" in tool_names

    @pytest.mark.anyio
    async def test_summarize_farm_observations_tool(self, server) -> None:
        """Verify executing summarize_farm_observations tool via MCP call."""
        await server.call_tool("record_farm_observation", {"crop": "Wheat", "notes": "Rust spots identified."})
        await server.call_tool("record_farm_observation", {"crop": "Wheat", "notes": "Lodging after rain."})

        res = await server.call_tool("summarize_farm_observations", {"crop": "Wheat"})
        assert not res.is_error
        data = json.loads(res.content[0].text)
        assert data["status"] == "success"
        assert data["total_observations"] == 2
        assert "Wheat" in data["crop_distribution"]

    @pytest.mark.anyio
    async def test_calculate_agronomic_metrics_tool(self, server) -> None:
        """Verify executing calculate_agronomic_metrics tool via MCP call."""
        sample_weather = [
            {"date": "2026-10-10", "max_temp_c": 22.0, "min_temp_c": 10.0, "precipitation_mm": 0.0},
            {"date": "2026-10-11", "max_temp_c": 26.0, "min_temp_c": 12.0, "precipitation_mm": 5.0},
        ]
        res = await server.call_tool(
            "calculate_agronomic_metrics",
            {
                "daily_weather": sample_weather,
                "base_temperature_c": 10.0,
            },
        )
        assert not res.is_error
        data = json.loads(res.content[0].text)
        assert data["status"] == "success"
        assert "growing_degree_days" in data
        assert "precipitation_summary" in data
        assert data["precipitation_summary"]["cumulative_precipitation_mm"] == 5.0
