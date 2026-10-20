"""Automated tests for FastAPI endpoints in Agricultural MCP Assistant."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from agricultural_assistant.api.app import create_app
from agricultural_assistant.client.gemini_adapter import GeminiAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    """Mocked AgriculturalMCPClient for fast isolated API testing."""
    client = AsyncMock(spec=AgriculturalMCPClient)
    client._session = MagicMock()
    client.list_tools.return_value = []
    client.get_weather_forecast.return_value = {
        "status": "success",
        "provider": "Open-Meteo",
        "coordinates": {"latitude": 9.02, "longitude": 38.74},
        "daily_forecast": [
            {
                "date": "2026-10-21",
                "max_temperature_c": 24.5,
                "min_temperature_c": 12.0,
                "precipitation_mm": 3.2,
                "precipitation_probability_pct": 40,
            }
        ],
        "attribution": "Weather data by Open-Meteo.com",
    }
    client.search_crop_disease.return_value = {
        "status": "success",
        "crop": "coffee",
        "message": "Found 1 matching disease records.",
        "potential_matches": [
            {
                "disease_name": "Coffee Leaf Rust",
                "scientific_name": "Hemileia vastatrix",
                "relevance_score": 0.95,
                "common_symptoms": ["Yellow-orange powdery spots on underside of leaves"],
                "management_recommendations": ["Plant resistant varieties", "Pruning"],
                "source_reference": "EIAR Coffee Pathology Bulletin",
            }
        ],
        "diagnostic_disclaimer": "Advisory suggestions only.",
    }
    client.list_farm_observations.return_value = {
        "status": "success",
        "total_count": 2,
        "returned_count": 2,
        "observations": [
            {
                "id": 1,
                "crop": "Maize",
                "notes": "Fall armyworm caterpillar feeding damage",
                "growth_stage": "vegetative",
                "observed_at": "2026-10-20T10:00:00",
                "location_name": "Plot A",
            }
        ],
    }
    client.get_farm_observation.return_value = {
        "status": "success",
        "observation": {
            "id": 1,
            "crop": "Maize",
            "notes": "Fall armyworm caterpillar feeding damage",
            "growth_stage": "vegetative",
            "observed_at": "2026-10-20T10:00:00",
            "location_name": "Plot A",
        },
    }
    client.record_farm_observation.return_value = {
        "status": "success",
        "observation_id": 42,
        "message": "Farm observation recorded successfully.",
    }
    client.summarize_farm_observations.return_value = {
        "status": "success",
        "total_observations": 5,
        "crop_distribution": {"Maize": 3, "Coffee": 2},
        "confidence_note": "Sample size is adequate for seasonal trend review.",
    }
    client.calculate_agronomic_metrics.return_value = {
        "status": "success",
        "growing_degree_days": {"cumulative_gdd": 18.5, "base_temperature_c": 10.0},
        "precipitation_summary": {"cumulative_precipitation_mm": 12.4, "rainy_days_count": 2},
    }
    return client


@pytest.fixture
def mock_gemini_adapter() -> AsyncMock:
    """Mocked GeminiAdapter."""
    adapter = AsyncMock(spec=GeminiAdapter)
    adapter.run_prompt.return_value = {
        "status": "success",
        "response_type": "final_answer",
        "llm_response": "Based on the records, the symptoms suggest Coffee Leaf Rust.",
        "tool_calls_executed": [
            {
                "tool_name": "search_crop_disease",
                "arguments": {"crop_name": "coffee", "symptoms": "yellow spots"},
                "result": {"status": "success"},
            }
        ],
        "rounds_used": 1,
    }
    return adapter


@pytest.fixture
def test_client(mock_mcp_client: AsyncMock, mock_gemini_adapter: AsyncMock) -> TestClient:
    """TestClient configured with mocked dependencies."""
    settings = Settings(
        app_env="testing",
        gemini_api_key="mock-key",
        cors_origins=["http://localhost:5173"],
    )
    app = create_app(
        settings=settings,
        mcp_client=mock_mcp_client,
        gemini_adapter=mock_gemini_adapter,
    )
    return TestClient(app)


def test_health_endpoint(test_client: TestClient) -> None:
    resp = test_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Agricultural MCP Assistant"


def test_chat_endpoint(test_client: TestClient, mock_gemini_adapter: AsyncMock) -> None:
    payload = {"prompt": "What is affecting my coffee leaves?", "conversation_history": []}
    resp = test_client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "Coffee Leaf Rust" in data["llm_response"]
    assert len(data["tool_calls_executed"]) == 1
    mock_gemini_adapter.run_prompt.assert_called_once()


def test_weather_endpoint_valid(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    resp = test_client.get("/api/weather/forecast?latitude=9.02&longitude=38.74&forecast_days=3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["provider"] == "Open-Meteo"
    mock_mcp_client.get_weather_forecast.assert_called_once()


def test_weather_endpoint_invalid_coords(test_client: TestClient) -> None:
    resp = test_client.get("/api/weather/forecast?latitude=999.0&longitude=38.74")
    assert resp.status_code == 422


def test_diseases_search_endpoint(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    resp = test_client.get("/api/diseases/search?crop_name=coffee&symptoms=yellow%20spots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["potential_matches"]) == 1
    mock_mcp_client.search_crop_disease.assert_called_once()


def test_list_observations_endpoint(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    resp = test_client.get("/api/observations?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total_count"] == 2
    mock_mcp_client.list_farm_observations.assert_called_once()


def test_get_observation_by_id(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    resp = test_client.get("/api/observations/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["observation"]["id"] == 1


def test_observation_preview_validation(test_client: TestClient) -> None:
    # Valid preview
    valid_payload = {
        "crop": "Teff",
        "notes": "Observed lodging after heavy rain",
        "growth_stage": "maturity",
        "location_name": "Field 3",
    }
    resp = test_client.post("/api/observations/preview", json=valid_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "valid"
    assert data["requires_confirmation"] is True
    assert data["preview"]["crop"] == "Teff"

    # Invalid preview (notes too short)
    bad_payload = {"crop": "Teff", "notes": "bad"}
    bad_resp = test_client.post("/api/observations/preview", json=bad_payload)
    assert bad_resp.status_code == 422


def test_observation_confirm_persists(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    payload = {
        "crop": "Coffee",
        "notes": "Dark sunken lesions on green berries",
        "growth_stage": "flowering",
        "location_name": "Jimma Block 2",
    }
    resp = test_client.post("/api/observations/confirm", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["observation_id"] == 42
    mock_mcp_client.record_farm_observation.assert_called_once_with(
        crop="Coffee",
        notes="Dark sunken lesions on green berries",
        growth_stage="flowering",
        location_name="Jimma Block 2",
        latitude=None,
        longitude=None,
        observer_role=None,
    )


def test_summarize_observations_endpoint(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    resp = test_client.get("/api/observations/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total_observations"] == 5


def test_agronomic_metrics_endpoint(test_client: TestClient, mock_mcp_client: AsyncMock) -> None:
    payload = {
        "daily_weather": [
            {"date": "Day 1", "max_temp_c": 25.0, "min_temp_c": 12.0, "precipitation_mm": 2.0}
        ],
        "base_temperature_c": 10.0,
    }
    resp = test_client.post("/api/metrics/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "growing_degree_days" in data
