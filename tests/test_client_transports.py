"""Automated tests for dual MCP transports (stdio & Streamable HTTP) and MCP primitives discovery."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from agricultural_assistant.api.app import create_app
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings


@pytest.fixture
def mock_dual_mcp_client() -> AsyncMock:
    """Mock AgriculturalMCPClient supporting dual transport tests."""
    client = AsyncMock(spec=AgriculturalMCPClient)
    client._session = MagicMock()
    client.is_connected = True
    client.transport = "stdio"
    client.server_url = "http://127.0.0.1:8000/mcp"
    client.bearer_token = None
    client.server_command = "uv"
    client.server_args = ["run", "agricultural-assistant-server"]

    # Mock tools
    t1 = MagicMock(); t1.name = "search_crop_disease"; t1.description = "Search crop diseases"; t1.input_schema = {"type": "object"}
    t2 = MagicMock(); t2.name = "get_weather_forecast"; t2.description = "Get weather forecast"; t2.input_schema = {"type": "object"}
    client.list_tools.return_value = [t1, t2]

    # Mock resources
    r1 = MagicMock(); r1.uri = "crops://catalog"; r1.name = "Crop Reference Catalog"; r1.description = "Catalog"; r1.mimeType = "application/json"
    client.list_resources.return_value = [r1]
    client.read_resource.return_value = '{"supported_crops": ["Teff", "Coffee"]}'

    # Mock prompts
    p1 = MagicMock(); p1.name = "agricultural_advisory_prompt"; p1.description = "Prompt template"; p1.arguments = []
    client.list_prompts.return_value = [p1]

    client.get_status.return_value = {
        "transport": "stdio",
        "is_connected": True,
        "server_url": None,
        "subprocess_command": "uv run agricultural-assistant-server",
        "has_bearer_token": False,
        "connected_at": 1729500000.0,
        "last_error": None,
        "cached_tools_count": 2,
    }
    return client


@pytest.fixture
def test_client(mock_dual_mcp_client: AsyncMock) -> TestClient:
    """TestClient configured with dual MCP client fixture."""
    app = create_app(
        settings=Settings(app_env="testing"),
        mcp_client=mock_dual_mcp_client,
    )
    with TestClient(app) as client:
        yield client


class TestClientTransportsAndPrimitives:
    """Test transport status, dynamic switching, and discoverability endpoints."""

    def test_mcp_status_endpoint(self, test_client: TestClient) -> None:
        """GET /api/mcp/status returns accurate diagnostics for connected transport."""
        resp = test_client.get("/api/mcp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["transport"] == "stdio"
        assert data["is_connected"] is True
        assert data["tools_count"] == 2

    def test_inspect_tools_endpoint(self, test_client: TestClient) -> None:
        """GET /api/mcp/tools returns discovered tools and typed schemas."""
        resp = test_client.get("/api/mcp/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["count"] == 2
        tool_names = [t["name"] for t in data["tools"]]
        assert "search_crop_disease" in tool_names
        assert "get_weather_forecast" in tool_names

    def test_inspect_resources_endpoint(self, test_client: TestClient) -> None:
        """GET /api/mcp/resources returns registered MCP resources."""
        resp = test_client.get("/api/mcp/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["count"] >= 1
        assert "crops://catalog" in [r["uri"] for r in data["resources"]]

    def test_read_resource_endpoint(self, test_client: TestClient) -> None:
        """GET /api/mcp/resources/read retrieves resource contents by URI."""
        resp = test_client.get("/api/mcp/resources/read?uri=crops://catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "Teff" in str(data["content"])

    def test_inspect_prompts_endpoint(self, test_client: TestClient) -> None:
        """GET /api/mcp/prompts returns registered prompt templates."""
        resp = test_client.get("/api/mcp/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["prompts"]) >= 1
        assert data["prompts"][0]["name"] == "agricultural_advisory_prompt"

    def test_transport_switching_endpoint(self, test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """POST /api/mcp/transport initiates client reconnection to target transport."""
        monkeypatch.setattr(AgriculturalMCPClient, "connect", AsyncMock())
        monkeypatch.setattr(AgriculturalMCPClient, "list_tools", AsyncMock(return_value=[]))
        resp = test_client.post(
            "/api/mcp/transport",
            json={
                "transport": "streamable-http",
                "server_url": "http://127.0.0.1:8000/mcp",
                "bearer_token": "valid-test-token",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["transport"] == "streamable-http"
        assert "streamable-http" in data["message"]
