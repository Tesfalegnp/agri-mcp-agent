"""Comprehensive unit and integration tests for OpenAI tool calling in LLMAdapter."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import openai
import pytest
from mcp.types import Tool

from agricultural_assistant.client.llm_adapter import (
    LLMAdapter,
    convert_mcp_tool_to_openai,
)
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings


def make_mock_completion(
    content: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> SimpleNamespace:
    """Create a mock OpenAI chat completion response structure."""
    tc_objects = []
    if tool_calls:
        for idx, tc in enumerate(tool_calls):
            raw_args = tc.get("arguments", {})
            args_str = json.dumps(raw_args) if isinstance(raw_args, dict) else str(raw_args)
            tc_objects.append(
                SimpleNamespace(
                    id=tc.get("id", f"call_{idx + 1}"),
                    type="function",
                    function=SimpleNamespace(
                        name=tc["name"],
                        arguments=args_str,
                    ),
                )
            )

    msg = SimpleNamespace(
        role="assistant",
        content=content,
        tool_calls=tc_objects if tool_calls else None,
    )
    choice = SimpleNamespace(
        message=msg,
        finish_reason="tool_calls" if tool_calls else "stop",
        index=0,
    )
    return SimpleNamespace(choices=[choice])


@pytest.fixture
def standard_mcp_tools() -> List[Tool]:
    """Standard list of MCP tools mirroring Phase 5 capabilities."""
    return [
        Tool(
            name="search_crop_disease",
            description="Search crop diseases by symptoms.",
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
            description="Get localized weather forecast.",
            input_schema={
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "forecast_days": {"type": "integer"},
                },
                "required": ["latitude", "longitude"],
            },
        ),
        Tool(
            name="record_farm_observation",
            description="Persist farm observation into SQLite.",
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
            description="Count recorded farm observations.",
            input_schema={
                "type": "object",
                "properties": {"crop": {"type": "string"}},
            },
        ),
    ]


class TestLLMAdapterOrchestration:
    """Test suite verifying all 14 Phase 6 tool-calling requirements."""

    # 1. Environment and configuration loading without exposing secrets
    def test_environment_loading_and_secret_protection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret_key = "sk-live-secret-never-expose"
        monkeypatch.setenv("OPENAI_API_KEY", secret_key)
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        monkeypatch.setenv("MAX_TOOL_ROUNDS", "4")

        adapter = LLMAdapter()
        assert adapter.is_available()
        assert adapter.model == "gpt-4o"
        assert adapter.max_tool_iterations == 4

        # Verify repr on settings masks the secret
        settings = Settings(openai_api_key=secret_key)
        assert secret_key not in repr(settings)
        assert "***" in repr(settings)

    # 2. Conversion of discovered MCP tools into valid model-tool schemas
    def test_mcp_tool_conversion_to_openai_schema(self, standard_mcp_tools: List[Tool]) -> None:
        crop_tool = standard_mcp_tools[0]
        schema = convert_mcp_tool_to_openai(crop_tool)

        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == "search_crop_disease"
        assert fn["description"] == "Search crop diseases by symptoms."
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "crop_name" in params["properties"]
        assert "symptoms" in params["properties"]
        assert params["required"] == ["crop_name", "symptoms"]

    # 3. User request that requires no tool
    @pytest.mark.anyio
    async def test_user_request_requires_no_tool(self, standard_mcp_tools: List[Tool]) -> None:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=make_mock_completion(content="Hello! I can help you with crop advice.")
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt("Hello assistant", mock_mcp_client)

        assert result["status"] == "success"
        assert result["response_type"] == "final_answer"
        assert "Hello! I can help you" in result["llm_response"]
        assert len(result["tool_calls_executed"]) == 0
        assert result["rounds_used"] == 1
        mock_openai.chat.completions.create.assert_called_once()

    # 4. One model-requested tool call executed through the MCP client
    # 5. Actual tool results returned to the model in the correct format
    # 7. Final answer generated from returned tool results
    @pytest.mark.anyio
    async def test_single_tool_call_flow(self, standard_mcp_tools: List[Tool]) -> None:
        tool_call_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_disease_1",
                    "name": "search_crop_disease",
                    "arguments": {"crop_name": "coffee", "symptoms": "dark lesions on berries"},
                }
            ]
        )
        final_resp = make_mock_completion(
            content="Based on the knowledge base, these symptoms match Coffee Berry Disease (CBD). Consult local extension agronomists."
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(side_effect=[tool_call_resp, final_resp])

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools
        mock_mcp_client.search_crop_disease.return_value = {
            "status": "success",
            "potential_matches": [
                {
                    "disease_name": "Coffee Berry Disease",
                    "scientific_name": "Colletotrichum kahawae",
                    "source_reference": "Jimma Agricultural Research Center Bulletin",
                }
            ],
        }

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt(
            "What disease causes dark lesions on coffee berries?", mock_mcp_client
        )

        assert result["status"] == "success"
        assert result["response_type"] == "final_answer"
        assert "Coffee Berry Disease" in result["llm_response"]
        assert len(result["tool_calls_executed"]) == 1
        assert result["tool_calls_executed"][0]["tool_name"] == "search_crop_disease"
        mock_mcp_client.search_crop_disease.assert_called_once_with(
            crop_name="coffee", symptoms="dark lesions on berries"
        )

        # Verify second call to OpenAI received role='tool' message with tool_call_id
        second_call_messages = mock_openai.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call_disease_1"
        tool_content = json.loads(tool_msgs[0]["content"])
        assert tool_content["status"] == "success"
        assert tool_content["potential_matches"][0]["disease_name"] == "Coffee Berry Disease"

    # 6. Multiple tool calls in a single turn and multiple rounds
    @pytest.mark.anyio
    async def test_multiple_tool_calls_in_single_turn(
        self, standard_mcp_tools: List[Tool]
    ) -> None:
        multi_tool_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_weather_1",
                    "name": "get_weather_forecast",
                    "arguments": {"latitude": 9.02, "longitude": 38.74, "forecast_days": 3},
                },
                {
                    "id": "call_count_1",
                    "name": "count_farm_observations",
                    "arguments": {"crop": "teff"},
                },
            ]
        )
        final_resp = make_mock_completion(
            content="Addis Ababa weather shows clear skies, and there are currently 4 recorded teff observations."
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[multi_tool_resp, final_resp]
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools
        mock_mcp_client.get_weather_forecast.return_value = {
            "status": "success",
            "provider": "Open-Meteo",
            "daily_forecast": [],
        }
        mock_mcp_client.count_farm_observations.return_value = {
            "status": "success",
            "count": 4,
        }

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt(
            "Check the weather in Addis and count our teff observations", mock_mcp_client
        )

        assert result["status"] == "success"
        assert len(result["tool_calls_executed"]) == 2
        mock_mcp_client.get_weather_forecast.assert_called_once()
        mock_mcp_client.count_farm_observations.assert_called_once()

        # Verify second call had both tool results
        second_call_messages = mock_openai.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 2
        assert {m["tool_call_id"] for m in tool_msgs} == {"call_weather_1", "call_count_1"}

    # 8. Invalid arguments and unknown tool names handling
    @pytest.mark.anyio
    async def test_invalid_arguments_and_unknown_tools_handling(
        self, standard_mcp_tools: List[Tool]
    ) -> None:
        malformed_args_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_bad_json",
                    "name": "search_crop_disease",
                    "arguments": "{bad_json: missing_quotes,",
                },
                {
                    "id": "call_unknown",
                    "name": "non_existent_fake_tool",
                    "arguments": {"param": 1},
                },
            ]
        )
        final_resp = make_mock_completion(
            content="I encountered invalid parameters and an unrecognized tool, so I could not retrieve those records."
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[malformed_args_resp, final_resp]
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt("Test error handling", mock_mcp_client)

        assert result["status"] == "success"
        executed = result["tool_calls_executed"]
        assert len(executed) == 2
        assert executed[0]["result"]["error_type"] == "malformed_json_arguments"
        assert executed[1]["result"]["error_type"] == "unknown_tool"

        # Verify neither called MCP client methods
        mock_mcp_client.search_crop_disease.assert_not_called()
        mock_mcp_client.call_tool.assert_not_called()

    # 9. OpenAI API errors, timeouts, and MCP failures
    @pytest.mark.anyio
    async def test_openai_api_timeout_error(self, standard_mcp_tools: List[Tool]) -> None:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=openai.APITimeoutError(request=MagicMock())
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt("Forecast tomorrow", mock_mcp_client)

        assert result["status"] == "error"
        assert result["error_type"] == "openai_timeout_error"

    @pytest.mark.anyio
    async def test_mcp_tool_execution_failure(self, standard_mcp_tools: List[Tool]) -> None:
        tool_call_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "get_weather_forecast",
                    "arguments": {"latitude": 9.0, "longitude": 38.0},
                }
            ]
        )
        final_resp = make_mock_completion(
            content="The weather service is temporarily unavailable. Please try again later."
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[tool_call_resp, final_resp]
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools
        mock_mcp_client.get_weather_forecast.side_effect = RuntimeError("Open-Meteo connection reset")

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt("Get weather", mock_mcp_client)

        assert result["status"] == "success"
        executed = result["tool_calls_executed"]
        assert len(executed) == 1
        assert executed[0]["result"]["error_type"] == "mcp_tool_execution_error"

    # 10. Maximum-round protection
    @pytest.mark.anyio
    async def test_maximum_round_protection(self, standard_mcp_tools: List[Tool]) -> None:
        infinite_tool_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_loop",
                    "name": "count_farm_observations",
                    "arguments": {"crop": "wheat"},
                }
            ]
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=infinite_tool_resp)

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools
        mock_mcp_client.count_farm_observations.return_value = {"status": "success", "count": 2}

        adapter = LLMAdapter(api_key="mock-key", max_tool_iterations=3, openai_client=mock_openai)
        result = await adapter.run_prompt("Loop forever query", mock_mcp_client)

        assert result["status"] == "max_iterations_reached"
        assert result["rounds_used"] == 3
        assert mock_openai.chat.completions.create.call_count == 3

    # 11. Write-operation confirmation before record_farm_observation (ACCEPTED)
    @pytest.mark.anyio
    async def test_write_operation_confirmation_accepted(
        self, standard_mcp_tools: List[Tool]
    ) -> None:
        write_call_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_write_1",
                    "name": "record_farm_observation",
                    "arguments": {"crop": "teff", "notes": "Rust pustules spotted on stems"},
                }
            ]
        )
        final_resp = make_mock_completion(
            content="Your observation has been authorized, confirmed, and saved to SQLite with ID #42."
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[write_call_resp, final_resp]
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools
        mock_mcp_client.record_farm_observation.return_value = {
            "status": "success",
            "observation_id": 42,
            "message": "Observation saved successfully.",
        }

        confirm_mock = MagicMock(return_value=True)

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt(
            "Record that my teff has rust pustules",
            mock_mcp_client,
            confirm_write_callback=confirm_mock,
        )

        assert result["status"] == "success"
        confirm_mock.assert_called_once_with(
            "record_farm_observation",
            {"crop": "teff", "notes": "Rust pustules spotted on stems"},
        )
        mock_mcp_client.record_farm_observation.assert_called_once_with(
            crop="teff", notes="Rust pustules spotted on stems"
        )
        assert "ID #42" in result["llm_response"]

    # 12. Cancellation or rejection of a proposed write
    # 13. Confirmation that rejected writes never reach the MCP server
    @pytest.mark.anyio
    async def test_write_operation_rejected_never_reaches_mcp_server(
        self, standard_mcp_tools: List[Tool]
    ) -> None:
        write_call_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_write_rejected",
                    "name": "record_farm_observation",
                    "arguments": {"crop": "maize", "notes": "Leaf damage"},
                }
            ]
        )
        final_resp = make_mock_completion(
            content="Understood. The write operation was cancelled and no observation was recorded."
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[write_call_resp, final_resp]
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools

        # User denies write confirmation
        confirm_mock = MagicMock(return_value=False)

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt(
            "Record maize damage",
            mock_mcp_client,
            confirm_write_callback=confirm_mock,
        )

        assert result["status"] == "success"
        confirm_mock.assert_called_once()
        # CRITICAL SAFETY: Rejected write MUST NEVER call record_farm_observation or call_tool
        mock_mcp_client.record_farm_observation.assert_not_called()
        mock_mcp_client.call_tool.assert_not_called()

        executed = result["tool_calls_executed"]
        assert len(executed) == 1
        assert executed[0]["cancelled"] is True
        assert executed[0]["result"]["status"] == "cancelled"

    # Read-only tools bypass write confirmation
    @pytest.mark.anyio
    async def test_read_only_tools_bypass_write_confirmation(
        self, standard_mcp_tools: List[Tool]
    ) -> None:
        read_call_resp = make_mock_completion(
            tool_calls=[
                {
                    "id": "call_read_1",
                    "name": "get_weather_forecast",
                    "arguments": {"latitude": 9.02, "longitude": 38.74},
                }
            ]
        )
        final_resp = make_mock_completion(content="Weather data loaded.")

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[read_call_resp, final_resp]
        )

        mock_mcp_client = AsyncMock(spec=AgriculturalMCPClient)
        mock_mcp_client.list_tools.return_value = standard_mcp_tools
        mock_mcp_client.get_weather_forecast.return_value = {
            "status": "success",
            "daily_forecast": [],
        }

        confirm_mock = MagicMock(return_value=False)

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)
        result = await adapter.run_prompt(
            "What is the forecast?",
            mock_mcp_client,
            confirm_write_callback=confirm_mock,
        )

        assert result["status"] == "success"
        # Confirm mock should NOT be called for read-only tools
        confirm_mock.assert_not_called()
        mock_mcp_client.get_weather_forecast.assert_called_once()
