"""Unit and integration tests for Google Gemini tool calling in GeminiAdapter."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from mcp.types import Tool

from agricultural_assistant.client.gemini_adapter import (
    GeminiAdapter,
    convert_mcp_tool_to_gemini,
)
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings


@pytest.fixture
def sample_mcp_tools() -> List[Tool]:
    """Sample MCP tools for testing."""
    return [
        Tool(
            name="search_crop_disease",
            description="Search disease knowledge base",
            input_schema={
                "type": "object",
                "properties": {
                    "crop_name": {"type": "string"},
                    "symptoms": {"type": "string"},
                },
                "required": ["crop_name", "symptoms"],
            },
        ),
        Tool(
            name="get_weather_forecast",
            description="Get localized weather forecast",
            input_schema={
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["latitude", "longitude"],
            },
        ),
        Tool(
            name="record_farm_observation",
            description="Persist farm observation into SQLite",
            input_schema={
                "type": "object",
                "properties": {
                    "crop": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["crop", "notes"],
            },
        ),
        Tool(
            name="count_farm_observations",
            description="Count farm observations in SQLite",
            input_schema={
                "type": "object",
                "properties": {"crop": {"type": "string"}},
            },
        ),
    ]


def make_mock_candidate(
    text: str | None = None,
    function_calls: list[tuple[str, dict[str, Any]]] | None = None,
) -> SimpleNamespace:
    """Create a mock Gemini response candidate."""
    parts = []
    if text:
        parts.append(SimpleNamespace(text=text, function_call=None))
    if function_calls:
        for name, args in function_calls:
            fc = SimpleNamespace(name=name, args=args)
            parts.append(SimpleNamespace(text=None, function_call=fc))

    content = SimpleNamespace(role="model", parts=parts)
    return SimpleNamespace(content=content)


def make_mock_gemini_response(
    text: str | None = None,
    function_calls: list[tuple[str, dict[str, Any]]] | None = None,
) -> SimpleNamespace:
    """Create a mock Gemini generate_content response."""
    cand = make_mock_candidate(text=text, function_calls=function_calls)
    return SimpleNamespace(candidates=[cand], text=text)


class TestGeminiAdapter:
    """Comprehensive test suite for GeminiAdapter."""

    def test_initialization_and_secret_masking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        secret_key = "gemini-secret-test-key-12345"
        monkeypatch.setenv("GEMINI_API_KEY", secret_key)
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

        adapter = GeminiAdapter()
        assert adapter.is_available()
        assert adapter.model == "gemini-2.5-flash"

        settings = Settings(gemini_api_key=secret_key)
        assert secret_key not in repr(settings)
        assert "***" in repr(settings)

    def test_mcp_tool_conversion_to_gemini(self, sample_mcp_tools: List[Tool]) -> None:
        disease_tool = sample_mcp_tools[0]
        fd = convert_mcp_tool_to_gemini(disease_tool)

        assert fd.name == "search_crop_disease"
        assert fd.description == "Search disease knowledge base"
        params = fd.parameters
        assert hasattr(params, "properties")
        assert "crop_name" in params.properties
        assert "symptoms" in params.properties
        assert "crop_name" in params.required

    @pytest.mark.anyio
    async def test_user_request_requires_no_tool(self, sample_mcp_tools: List[Tool]) -> None:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = make_mock_gemini_response(
            text="Hello farmer! How can I assist with your crops today?"
        )

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools

        adapter = GeminiAdapter(api_key="mock-key", client=mock_client)
        result = await adapter.run_prompt("Hello!", mock_mcp)

        assert result["status"] == "success"
        assert result["response_type"] == "final_answer"
        assert "Hello farmer!" in result["llm_response"]
        assert len(result["tool_calls_executed"]) == 0
        assert result["rounds_used"] == 1

    @pytest.mark.anyio
    async def test_single_tool_call_flow(self, sample_mcp_tools: List[Tool]) -> None:
        # Turn 1: Model requests disease search
        resp_turn1 = make_mock_gemini_response(
            function_calls=[("search_crop_disease", {"crop_name": "coffee", "symptoms": "dark lesions on berries"})]
        )
        # Turn 2: Model returns final diagnosis based on tool output
        resp_turn2 = make_mock_gemini_response(
            text="Based on agricultural records, this is Coffee Berry Disease (CBD). Practice field sanitation."
        )

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_turn1, resp_turn2]

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools
        mock_mcp.search_crop_disease.return_value = {
            "status": "success",
            "potential_matches": [
                {
                    "disease_name": "Coffee Berry Disease",
                    "scientific_name": "Colletotrichum kahawae",
                    "source_reference": "EIAR Research Bulletin",
                }
            ],
        }

        adapter = GeminiAdapter(api_key="mock-key", client=mock_client)
        result = await adapter.run_prompt("What disease causes dark lesions on coffee berries?", mock_mcp)

        assert result["status"] == "success"
        assert "Coffee Berry Disease" in result["llm_response"]
        assert len(result["tool_calls_executed"]) == 1
        executed = result["tool_calls_executed"][0]
        assert executed["tool_name"] == "search_crop_disease"
        assert executed["arguments"]["crop_name"] == "coffee"
        mock_mcp.search_crop_disease.assert_called_once_with(
            crop_name="coffee", symptoms="dark lesions on berries"
        )

    @pytest.mark.anyio
    async def test_multiple_tool_calls_in_single_turn(self, sample_mcp_tools: List[Tool]) -> None:
        resp_turn1 = make_mock_gemini_response(
            function_calls=[
                ("get_weather_forecast", {"latitude": 9.02, "longitude": 38.74}),
                ("count_farm_observations", {"crop": "teff"}),
            ]
        )
        resp_turn2 = make_mock_gemini_response(
            text="Weather in Addis Ababa is mild, and there are currently 3 teff observations."
        )

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_turn1, resp_turn2]

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools
        mock_mcp.get_weather_forecast.return_value = {"status": "success", "daily_forecast": []}
        mock_mcp.count_farm_observations.return_value = {"status": "success", "count": 3}

        adapter = GeminiAdapter(api_key="mock-key", client=mock_client)
        result = await adapter.run_prompt("Check weather and teff count", mock_mcp)

        assert result["status"] == "success"
        assert len(result["tool_calls_executed"]) == 2
        mock_mcp.get_weather_forecast.assert_called_once()
        mock_mcp.count_farm_observations.assert_called_once()

    @pytest.mark.anyio
    async def test_write_operation_confirmation_accepted(self, sample_mcp_tools: List[Tool]) -> None:
        resp_turn1 = make_mock_gemini_response(
            function_calls=[("record_farm_observation", {"crop": "maize", "notes": "Leaf chlorosis"})]
        )
        resp_turn2 = make_mock_gemini_response(text="Observation saved successfully with ID #12.")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_turn1, resp_turn2]

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools
        mock_mcp.record_farm_observation.return_value = {
            "status": "success",
            "observation_id": 12,
            "message": "Observation saved.",
        }

        confirm_mock = MagicMock(return_value=True)

        adapter = GeminiAdapter(api_key="mock-key", client=mock_client)
        result = await adapter.run_prompt(
            "Record maize leaf chlorosis", mock_mcp, confirm_write_callback=confirm_mock
        )

        assert result["status"] == "success"
        confirm_mock.assert_called_once_with(
            "record_farm_observation", {"crop": "maize", "notes": "Leaf chlorosis"}
        )
        mock_mcp.record_farm_observation.assert_called_once_with(
            crop="maize", notes="Leaf chlorosis"
        )
        assert "ID #12" in result["llm_response"]

    @pytest.mark.anyio
    async def test_write_operation_rejected_never_calls_mcp_server(
        self, sample_mcp_tools: List[Tool]
    ) -> None:
        resp_turn1 = make_mock_gemini_response(
            function_calls=[("record_farm_observation", {"crop": "coffee", "notes": "Berry drop"})]
        )
        resp_turn2 = make_mock_gemini_response(
            text="The write operation was cancelled and no observation was recorded."
        )

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_turn1, resp_turn2]

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools

        confirm_mock = MagicMock(return_value=False)

        adapter = GeminiAdapter(api_key="mock-key", client=mock_client)
        result = await adapter.run_prompt(
            "Record coffee berry drop", mock_mcp, confirm_write_callback=confirm_mock
        )

        assert result["status"] == "success"
        confirm_mock.assert_called_once()
        # CRITICAL SAFETY: Rejected write MUST NEVER call record_farm_observation
        mock_mcp.record_farm_observation.assert_not_called()
        mock_mcp.call_tool.assert_not_called()

        executed = result["tool_calls_executed"]
        assert len(executed) == 1
        assert executed[0]["cancelled"] is True
        assert executed[0]["result"]["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_quota_exhaustion_handling(self, sample_mcp_tools: List[Tool]) -> None:
        mock_client = MagicMock()
        api_err = genai_errors.APIError(
            code=429,
            response_json={"error": {"message": "Resource has been exhausted (e.g. check quota)."}},
        )
        mock_client.models.generate_content.side_effect = api_err

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools

        adapter = GeminiAdapter(api_key="mock-key", client=mock_client)
        result = await adapter.run_prompt("Any question", mock_mcp)

        assert result["status"] == "error"
        assert result["error_type"] == "gemini_quota_exhausted"
        assert "quota exhausted" in result["message"].lower()

    @pytest.mark.anyio
    async def test_maximum_round_protection(self, sample_mcp_tools: List[Tool]) -> None:
        infinite_call = make_mock_gemini_response(
            function_calls=[("count_farm_observations", {"crop": "wheat"})]
        )
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = infinite_call

        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools
        mock_mcp.count_farm_observations.return_value = {"status": "success", "count": 1}

        adapter = GeminiAdapter(api_key="mock-key", max_tool_iterations=3, client=mock_client)
        result = await adapter.run_prompt("Infinite loop query", mock_mcp)

        assert result["status"] == "max_iterations_reached"
        assert result["rounds_used"] == 3
        assert mock_client.models.generate_content.call_count == 3

    @pytest.mark.anyio
    async def test_deterministic_offline_fallback(self, sample_mcp_tools: List[Tool]) -> None:
        mock_mcp = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp.list_tools.return_value = sample_mcp_tools
        mock_mcp.search_crop_disease.return_value = {
            "status": "success",
            "potential_matches": [
                {
                    "disease_name": "Coffee Leaf Rust",
                    "scientific_name": "Hemileia vastatrix",
                    "management_recommendations": ["Prune shaded branches", "Apply copper fungicide"],
                    "source_reference": "EIAR Coffee Pathology Unit",
                }
            ],
            "diagnostic_disclaimer": "Consult local extension officer.",
        }

        # Adapter initialized with no API key (offline / fallback mode)
        adapter = GeminiAdapter(api_key=None, client=None)
        result = await adapter.run_prompt("What are symptoms of coffee rust disease?", mock_mcp)

        assert result["status"] == "success"
        assert "Coffee Leaf Rust" in result["llm_response"]
        assert len(result["tool_calls_executed"]) == 1
        mock_mcp.search_crop_disease.assert_called_once()
