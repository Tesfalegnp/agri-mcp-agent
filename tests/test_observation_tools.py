"""Integration tests for MCP farm observation tools."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from agricultural_assistant.server.app import create_server
from agricultural_assistant.services.observation_service import ObservationService
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.observation_repository import ObservationRepository


class TestObservationTools:
    """Test suite for MCP farm observation tools."""

    @pytest.fixture
    def server(self, tmp_path: Path):
        db_path = tmp_path / "obs_tools_test.db"
        db = DatabaseManager(db_path)
        db.initialize()
        repo = ObservationRepository(db)
        obs_service = ObservationService(repo)
        return create_server(observation_service=obs_service)

    @pytest.mark.anyio
    async def test_tool_discovery_includes_observation_tools(self, server) -> None:
        """Verify server registers all four observation tools."""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]

        assert "record_farm_observation" in tool_names
        assert "get_farm_observation" in tool_names
        assert "list_farm_observations" in tool_names
        assert "count_farm_observations" in tool_names

    @pytest.mark.anyio
    async def test_record_and_get_observation_tool_calls(self, server) -> None:
        """Verify recording and then retrieving an observation via MCP call_tool."""
        # 1. Record an observation
        record_res = await server.call_tool(
            "record_farm_observation",
            {
                "crop": "Coffee",
                "notes": "Small rust spots identified on leaves in northern sector.",
                "growth_stage": "flowering",
                "location_name": "Jimma plot 1",
                "latitude": 7.67,
                "longitude": 36.83,
                "observer_role": "agronomist",
            },
        )
        assert not record_res.is_error
        record_data = json.loads(record_res.content[0].text)
        assert record_data["status"] == "success"
        obs_id = record_data["observation_id"]

        # 2. Retrieve observation by ID
        get_res = await server.call_tool("get_farm_observation", {"observation_id": obs_id})
        assert not get_res.is_error
        get_data = json.loads(get_res.content[0].text)
        assert get_data["status"] == "success"
        assert get_data["observation"]["id"] == obs_id
        assert get_data["observation"]["crop"] == "Coffee"

    @pytest.mark.anyio
    async def test_list_and_count_observation_tools(self, server) -> None:
        """Verify list_farm_observations and count_farm_observations tool execution."""
        await server.call_tool("record_farm_observation", {"crop": "Teff", "notes": "Lodging noted."})
        await server.call_tool("record_farm_observation", {"crop": "Maize", "notes": "FAW caterpillars."})

        # List
        list_res = await server.call_tool("list_farm_observations", {"crop": "teff"})
        list_data = json.loads(list_res.content[0].text)
        assert list_data["status"] == "success"
        assert list_data["total_count"] == 1
        assert list_data["observations"][0]["crop"] == "Teff"

        # Count
        count_res = await server.call_tool("count_farm_observations", {})
        count_data = json.loads(count_res.content[0].text)
        assert count_data["status"] == "success"
        assert count_data["count"] == 2
