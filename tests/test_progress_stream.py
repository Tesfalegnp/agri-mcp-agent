"""Automated tests for Server-Sent Events (SSE) live execution progress streaming."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from agricultural_assistant.api.app import create_app
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    """Mock AgriculturalMCPClient for fast streaming tests."""
    client = AsyncMock(spec=AgriculturalMCPClient)
    client._session = MagicMock()
    client.is_connected = True
    client.transport = "stdio"

    t1 = MagicMock(); t1.name = "search_crop_disease"; t1.description = "Search crop diseases"; t1.input_schema = {}
    client.list_tools.return_value = [t1]
    client.search_crop_disease.return_value = {
        "status": "success",
        "crop": "Coffee",
        "potential_matches": [],
    }
    return client


@pytest.fixture
def test_client(mock_mcp_client: AsyncMock) -> TestClient:
    app = create_app(
        settings=Settings(app_env="testing"),
        mcp_client=mock_mcp_client,
    )
    with TestClient(app) as client:
        yield client


class TestLiveProgressSSEStream:
    """Test live Server-Sent Events streaming endpoint."""

    def test_sse_stream_events_structure(self, test_client: TestClient) -> None:
        """Stream /api/chat/stream and verify real-time event types, timestamps, and steps."""
        response = test_client.get(
            "/api/chat/stream?prompt=What%20disease%20causes%20spots%20on%20coffee%20leaves%3F",
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        body_lines = response.text.split("\n")
        events = []
        current_event = {}

        for line in body_lines:
            if line.startswith("event: "):
                current_event["type"] = line[7:].strip()
            elif line.startswith("data: "):
                current_event["data"] = json.loads(line[6:].strip())
            elif line == "":
                if current_event:
                    events.append(current_event)
                    current_event = {}

        assert len(events) >= 2

        # Verify progress events
        progress_events = [e for e in events if e["type"] == "progress"]
        assert len(progress_events) >= 1

        steps = [e["data"]["step"] for e in progress_events]
        assert "request_received" in steps
        assert "context_loaded" in steps

        # Verify done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        done_payload = done_events[0]["data"]
        assert done_payload["status"] == "success"
        assert "llm_response" in done_payload
        assert "conversation_id" in done_payload

    def test_sse_stream_post_payload(self, test_client: TestClient) -> None:
        """POST /api/chat/stream accepts JSON body with conversation_id."""
        response = test_client.post(
            "/api/chat/stream",
            json={
                "prompt": "Tell me about maize armyworm prevention",
                "conversation_id": "test-stream-conv-1",
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "test-stream-conv-1" in response.text

    def test_sse_stream_handles_client_error_gracefully(self, test_client: TestClient) -> None:
        """Stream gracefully handles missing prompt parameter with 400 Bad Request."""
        response = test_client.get("/api/chat/stream")
        assert response.status_code == 400
        assert "Missing required 'prompt'" in response.json()["detail"]

