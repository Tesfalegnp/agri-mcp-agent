"""Automated tests for Multi-Turn Conversation, Missing-Information Gathering, and Continuation.

Verifies:
- Detecting missing required parameters before attempting execution
- Asking one concise clarification question at a time
- Preserving session state, conversation ID, and collected slots
- Automatic workflow resumption once all required fields are provided
- User correction of earlier answers
- User cancellation of pending operations
- Safe session isolation between distinct conversation IDs
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.client.orchestrator import (
    ConversationOrchestrator,
    ConversationState,
    PendingWorkflow,
)


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    """Mock AgriculturalMCPClient returning valid weather and disease data."""
    client = AsyncMock(spec=AgriculturalMCPClient)
    client._session = MagicMock()
    client.is_connected = True
    client.transport = "stdio"

    # Registered tools mock
    t1 = MagicMock(); t1.name = "search_crop_disease"; t1.description = "Search crop diseases"; t1.input_schema = {}
    t2 = MagicMock(); t2.name = "get_weather_forecast"; t2.description = "Get weather forecast"; t2.input_schema = {}
    client.list_tools.return_value = [t1, t2]

    client.get_weather_forecast.return_value = {
        "status": "success",
        "provider": "Open-Meteo",
        "coordinates": {"latitude": 7.67, "longitude": 36.83},
        "daily_forecast": [
            {
                "date": "2026-10-22",
                "max_temperature_c": 26.0,
                "min_temperature_c": 14.5,
                "precipitation_mm": 2.0,
                "precipitation_probability_pct": 35,
            }
        ],
        "attribution": "Weather data by Open-Meteo.com",
    }

    client.search_crop_disease.return_value = {
        "status": "success",
        "crop": "Coffee",
        "potential_matches": [
            {
                "disease_name": "Coffee Leaf Rust",
                "scientific_name": "Hemileia vastatrix",
                "common_symptoms": ["Powdery orange spots"],
                "management_recommendations": ["Plant resistant cultivars", "Canopy pruning"],
                "source_reference": "EIAR Coffee Research Center",
            }
        ],
        "diagnostic_disclaimer": "Physical inspection recommended.",
    }

    return client


class TestMultiTurnConversations:
    """Test full multi-turn conversational advisory sequence."""

    @pytest.mark.anyio
    async def test_full_missing_information_gathering_and_resume(self, mock_mcp_client: AsyncMock) -> None:
        """Execute the exact demonstration sequence:
        Turn 1: "Help me prepare an agricultural advisory for my farm." -> asks for crop & location
        Turn 2: "Coffee, in Jimma, Ethiopia." -> asks for advisory topics
        Turn 3: "Weather risks and coffee leaf disease prevention." -> resumes workflow and returns grounded advisory
        """
        orch = ConversationOrchestrator()
        conv_id = "test-conv-flow-1"

        # Turn 1
        turn1 = await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn1["status"] == "awaiting_user_input"
        assert turn1["state"] == ConversationState.AWAITING_USER_INPUT.value
        assert "crop" in turn1["llm_response"].lower()
        assert "located" in turn1["llm_response"].lower() or "where" in turn1["llm_response"].lower()
        assert turn1["pending_workflow"] is not None
        assert "crop" in turn1["pending_workflow"]["missing_slots"]

        # Turn 2: User provides crop and location
        turn2 = await orch.process_user_turn(
            prompt="Coffee, in Jimma, Ethiopia.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn2["status"] == "awaiting_user_input"
        assert turn2["state"] == ConversationState.AWAITING_USER_INPUT.value
        # Assistant acknowledges Coffee and Jimma and asks for topics
        assert "weather risks" in turn2["llm_response"].lower() or "disease prevention" in turn2["llm_response"].lower()
        assert turn2["pending_workflow"]["collected_slots"]["crop"] == "Coffee"
        assert "Jimma" in turn2["pending_workflow"]["collected_slots"]["location"]

        # Turn 3: User specifies topics -> workflow resumes!
        turn3 = await orch.process_user_turn(
            prompt="Weather risks and coffee leaf disease prevention.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn3["status"] == "success"
        assert turn3["state"] == ConversationState.COMPLETED.value
        # MCP tools must have been called
        assert len(turn3["tool_calls_executed"]) >= 2
        tool_names = [tc["tool_name"] for tc in turn3["tool_calls_executed"]]
        assert "get_weather_forecast" in tool_names
        assert "search_crop_disease" in tool_names

        # Response must be grounded in actual tool findings
        resp_text = turn3["llm_response"]
        assert "Coffee Leaf Rust" in resp_text
        assert "Jimma" in resp_text
        assert "Open-Meteo" in resp_text or "Weather" in resp_text
        assert "EIAR" in resp_text

        # Ensure genuine execution activity events were recorded
        events = turn3["activity_events"]
        step_names = [e["step"] for e in events]
        assert "request_received" in step_names
        assert "context_loaded" in step_names
        assert "workflow_resumed" in step_names
        assert "final_answer_delivered" in step_names

    @pytest.mark.anyio
    async def test_user_cancellation(self, mock_mcp_client: AsyncMock) -> None:
        """User can cancel an active pending workflow at any time."""
        orch = ConversationOrchestrator()
        conv_id = "test-conv-cancel"

        # Turn 1: Start workflow
        await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        session = orch.get_or_create_session(conv_id)
        assert session.state == ConversationState.AWAITING_USER_INPUT

        # Turn 2: User says "cancel"
        turn2 = await orch.process_user_turn(
            prompt="Never mind, please cancel this.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn2["status"] == "cancelled"
        assert turn2["state"] == ConversationState.CANCELLED.value
        assert session.pending_workflow is None
        assert "cancelled" in turn2["llm_response"].lower()

    @pytest.mark.anyio
    async def test_user_slot_correction(self, mock_mcp_client: AsyncMock) -> None:
        """User can correct an earlier answer (e.g. changing crop from Coffee to Maize)."""
        orch = ConversationOrchestrator()
        conv_id = "test-conv-correction"

        # Start workflow
        await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )

        # User provides initial crop and location
        await orch.process_user_turn(
            prompt="Coffee in Jimma.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        session = orch.get_or_create_session(conv_id)
        assert session.pending_workflow.collected_slots["crop"] == "Coffee"

        # User corrects: "Actually I meant Maize, not coffee"
        turn3 = await orch.process_user_turn(
            prompt="Actually I meant Maize, please advise on weather risks and disease prevention.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn3["status"] == "success"
        # Tool execution must have used updated crop "Maize"
        disease_calls = [tc for tc in turn3["tool_calls_executed"] if tc["tool_name"] == "search_crop_disease"]
        assert len(disease_calls) > 0
        assert disease_calls[0]["arguments"]["crop_name"] == "Maize"

    @pytest.mark.anyio
    async def test_session_isolation(self, mock_mcp_client: AsyncMock) -> None:
        """Multiple concurrent sessions remain completely isolated."""
        orch = ConversationOrchestrator()

        # Session A: Farmer in Jimma with Coffee
        await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id="session-A",
            mcp_client=mock_mcp_client,
        )
        await orch.process_user_turn(
            prompt="Coffee in Jimma.",
            conversation_id="session-A",
            mcp_client=mock_mcp_client,
        )

        # Session B: Farmer in Hawassa with Wheat
        await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id="session-B",
            mcp_client=mock_mcp_client,
        )
        await orch.process_user_turn(
            prompt="Wheat in Hawassa.",
            conversation_id="session-B",
            mcp_client=mock_mcp_client,
        )

        sess_a = orch.get_or_create_session("session-A")
        sess_b = orch.get_or_create_session("session-B")

        assert sess_a.pending_workflow.collected_slots["crop"] == "Coffee"
        assert sess_a.pending_workflow.collected_slots["location"] == "Jimma"

        assert sess_b.pending_workflow.collected_slots["crop"] == "Wheat"
        assert sess_b.pending_workflow.collected_slots["location"] == "Hawassa"

    @pytest.mark.anyio
    async def test_single_missing_parameter(self, mock_mcp_client: AsyncMock) -> None:
        """Prompt provides location (Jimma) but omits crop; orchestrator prompts specifically for crop."""
        orch = ConversationOrchestrator()
        conv_id = "test-single-missing"

        # Turn 1: Farmer mentions location Jimma but no crop
        turn1 = await orch.process_user_turn(
            prompt="Give me an agricultural advisory for my farm in Jimma.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn1["status"] == "awaiting_user_input"
        assert "crop" in turn1["llm_response"].lower()
        # Location Jimma was already captured
        session = orch.get_or_create_session(conv_id)
        assert session.pending_workflow.collected_slots.get("location") == "Jimma"
        assert "crop" in session.pending_workflow.get_missing_slots()

        # Turn 2: Farmer supplies crop
        turn2 = await orch.process_user_turn(
            prompt="I am growing Coffee.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn2["status"] == "awaiting_user_input"
        assert session.pending_workflow.collected_slots.get("crop") == "Coffee"

    @pytest.mark.anyio
    async def test_uninformative_followup_remains_in_clarification(self, mock_mcp_client: AsyncMock) -> None:
        """When user replies without providing required slots, orchestrator remains in awaiting_user_input."""
        orch = ConversationOrchestrator()
        conv_id = "test-uninformative"

        # Turn 1: Initial ambiguous request
        await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )

        # Turn 2: Uninformative response
        turn2 = await orch.process_user_turn(
            prompt="I don't know what you mean, tell me what to do.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn2["status"] == "awaiting_user_input"
        assert turn2["state"] == ConversationState.AWAITING_USER_INPUT.value
        # Still awaiting crop and location
        session = orch.get_or_create_session(conv_id)
        assert "crop" in session.pending_workflow.get_missing_slots()
        assert "location" in session.pending_workflow.get_missing_slots()

    @pytest.mark.anyio
    async def test_tool_failure_during_resumed_workflow(self, mock_mcp_client: AsyncMock) -> None:
        """Tool failure during resumed workflow is safely caught, reported, and does not crash dialogue."""
        # Configure weather tool to fail with network error
        mock_mcp_client.get_weather_forecast.side_effect = RuntimeError("Open-Meteo gateway timeout")

        orch = ConversationOrchestrator()
        conv_id = "test-tool-failure"

        # Turn 1
        await orch.process_user_turn(
            prompt="Help me prepare an agricultural advisory for my farm.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        # Turn 2
        await orch.process_user_turn(
            prompt="Coffee in Jimma.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        # Turn 3: Triggers execution where weather tool fails
        turn3 = await orch.process_user_turn(
            prompt="Weather risks and coffee leaf disease prevention.",
            conversation_id=conv_id,
            mcp_client=mock_mcp_client,
        )
        assert turn3["status"] == "success"
        assert turn3["state"] == ConversationState.COMPLETED.value
        # Check event recorded error for weather tool
        event_steps = [e["step"] for e in turn3["activity_events"]]
        assert "tool_failed" in event_steps
        # Disease prevention information still delivered
        assert "Coffee Leaf Rust" in turn3["llm_response"]

