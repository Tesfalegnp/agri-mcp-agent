"""FastAPI routes for the Agricultural MCP Assistant HTTP backend."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery
from agricultural_assistant.domain.observation import FarmObservation
from agricultural_assistant.domain.weather import WeatherForecastRequest

logger = logging.getLogger("agricultural_assistant.api")

router = APIRouter(prefix="/api")


# --- Request & Response Models ---

class ChatRequest(BaseModel):
    """Payload for submitting a question to the AI assistant."""
    prompt: str = Field(..., min_length=1, description="Farmer natural language query")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Prior conversation turns [{'role': 'user'|'model', 'text': '...'}]"
    )
    auto_confirm_writes: bool = Field(
        default=False, description="If True, auto-approves write operations (e.g. from headless tests)"
    )


class ObservationInput(BaseModel):
    """Payload for previewing or confirming a farm observation."""
    crop: str = Field(..., min_length=2, description="Crop name (e.g. Maize, Coffee, Teff)")
    notes: str = Field(..., min_length=5, description="Observed field notes or symptoms")
    growth_stage: Optional[str] = Field(default=None, description="Phenological growth stage")
    location_name: Optional[str] = Field(default=None, description="Field or plot sector identifier")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="GPS Latitude (-90 to 90)")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="GPS Longitude (-180 to 180)")
    observer_role: Optional[str] = Field(default=None, description="Observer role (farmer, agronomist, scout)")


class AgronomicCalcRequest(BaseModel):
    """Payload for computing deterministic GDD and precipitation metrics."""
    daily_weather: List[Dict[str, Any]] = Field(..., min_length=1, description="List of daily weather records")
    base_temperature_c: float = Field(default=10.0, description="Base threshold temperature in °C")
    upper_cutoff_c: Optional[float] = Field(default=None, description="Upper threshold cutoff in °C")
    dry_day_threshold_mm: float = Field(default=1.0, description="Precipitation threshold for rainy day")


def _get_mcp_client(request: Request) -> AgriculturalMCPClient:
    """Retrieve MCP Client from app state or raise 503 if unavailable."""
    mcp_client = getattr(request.app.state, "mcp_client", None)
    if not mcp_client:
        raise HTTPException(
            status_code=503,
            detail="Agricultural MCP Client is not connected. Ensure the MCP server is running.",
        )
    return mcp_client


def _get_gemini_adapter(request: Request) -> GeminiAdapter:
    """Retrieve GeminiAdapter from app state with fallback."""
    adapter = getattr(request.app.state, "gemini_adapter", None)
    return adapter if adapter is not None else GeminiAdapter()


# --- Endpoints ---

@router.get("/health")
async def get_health(request: Request) -> Dict[str, Any]:
    """Return backend, database, and MCP server health status."""
    mcp_client = getattr(request.app.state, "mcp_client", None)
    is_connected = bool(mcp_client and getattr(mcp_client, "_session", None) is not None)
    tool_count = 0
    if is_connected:
        try:
            tools = await mcp_client.list_tools()
            tool_count = len(tools)
        except Exception:
            is_connected = False

    return {
        "status": "healthy" if is_connected else "degraded",
        "mcp_server_connected": is_connected,
        "tools_discovered": tool_count,
        "service": "Agricultural MCP Assistant",
        "version": "0.1.0",
    }


@router.post("/chat")
async def chat_with_assistant(payload: ChatRequest, request: Request) -> Dict[str, Any]:
    """Submit a natural-language question to the Gemini AI Assistant with MCP tool calling."""
    gemini_adapter = _get_gemini_adapter(request)
    mcp_client = _get_mcp_client(request)

    # Execute prompt through GeminiAdapter (with dynamic tool discovery and write-safety)
    result = await gemini_adapter.run_prompt(
        user_prompt=payload.prompt,
        mcp_client=mcp_client,
        auto_confirm_writes=payload.auto_confirm_writes,
        conversation_history=payload.conversation_history,
    )
    return result


@router.get("/weather/forecast")
async def get_weather(
    request: Request,
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude decimal degrees"),
    forecast_days: int = Query(default=3, ge=1, le=14, description="Forecast days (1-14)"),
    crop_context: Optional[str] = Query(default=None, description="Optional crop context"),
) -> Dict[str, Any]:
    """Retrieve localized meteorological forecast via Open-Meteo MCP tool."""
    mcp_client = _get_mcp_client(request)
    try:
        WeatherForecastRequest(
            latitude=latitude,
            longitude=longitude,
            forecast_days=forecast_days,
            crop_context=crop_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = await mcp_client.get_weather_forecast(
        latitude=latitude,
        longitude=longitude,
        forecast_days=forecast_days,
        crop_context=crop_context,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("message", "Weather service failure"))
    return result


@router.get("/diseases/search")
async def search_diseases(
    request: Request,
    crop_name: str = Query(..., min_length=2, description="Target crop (e.g. coffee, maize, teff)"),
    symptoms: str = Query(..., min_length=3, description="Observed symptom description"),
    growth_stage: Optional[str] = Query(default=None, description="Optional phenological stage"),
    language: str = Query(default="en", description="Language code (en, am, om, ti)"),
) -> Dict[str, Any]:
    """Search vetted agricultural pathology knowledge base using SQLite FTS5."""
    mcp_client = _get_mcp_client(request)
    parsed_stage = None
    if growth_stage:
        try:
            parsed_stage = CropGrowthStage(growth_stage.lower())
        except ValueError:
            pass

    try:
        CropSymptomQuery(
            crop_name=crop_name,
            symptoms=symptoms,
            growth_stage=parsed_stage,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = await mcp_client.search_crop_disease(
        crop_name=crop_name,
        symptoms=symptoms,
        growth_stage=parsed_stage.value if parsed_stage else None,
        language=language,
    )
    return result


@router.get("/observations")
async def list_observations(
    request: Request,
    crop: Optional[str] = Query(default=None, description="Filter by crop name"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> Dict[str, Any]:
    """List recorded farm observations with optional filtering."""
    mcp_client = _get_mcp_client(request)
    return await mcp_client.list_farm_observations(crop=crop, limit=limit, offset=offset)


@router.get("/observations/summary")
async def summarize_observations(
    request: Request,
    crop: Optional[str] = Query(default=None, description="Filter summary by crop"),
) -> Dict[str, Any]:
    """Retrieve statistical aggregations of historical farm observations."""
    mcp_client = _get_mcp_client(request)
    return await mcp_client.summarize_farm_observations(crop=crop)


@router.get("/observations/{observation_id}")
async def get_observation_by_id(observation_id: int, request: Request) -> Dict[str, Any]:
    """Retrieve a single farm observation by database ID."""
    mcp_client = _get_mcp_client(request)
    result = await mcp_client.get_farm_observation(observation_id=observation_id)
    if result.get("status") != "success":
        raise HTTPException(status_code=404, detail=result.get("message", "Observation not found"))
    return result


@router.post("/observations/preview")
async def preview_observation(payload: ObservationInput) -> Dict[str, Any]:
    """Validate observation input and return formatted preview for explicit farmer confirmation."""
    parsed_stage = None
    if payload.growth_stage:
        try:
            parsed_stage = CropGrowthStage(payload.growth_stage.lower())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid growth_stage '{payload.growth_stage}'. Allowed: {[s.value for s in CropGrowthStage]}",
            )

    try:
        obs = FarmObservation(
            crop=payload.crop,
            notes=payload.notes,
            growth_stage=parsed_stage,
            location_name=payload.location_name,
            latitude=payload.latitude,
            longitude=payload.longitude,
            observer_role=payload.observer_role,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "status": "valid",
        "preview": obs.model_dump(),
        "requires_confirmation": True,
        "message": "Review the observation details before confirming to save.",
    }


@router.post("/observations/confirm")
async def confirm_record_observation(payload: ObservationInput, request: Request) -> Dict[str, Any]:
    """Explicitly confirm and persist a new farm observation into SQLite via MCP."""
    mcp_client = _get_mcp_client(request)
    parsed_stage = None
    if payload.growth_stage:
        try:
            parsed_stage = CropGrowthStage(payload.growth_stage.lower())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid growth_stage '{payload.growth_stage}'. Allowed: {[s.value for s in CropGrowthStage]}",
            )

    try:
        FarmObservation(
            crop=payload.crop,
            notes=payload.notes,
            growth_stage=parsed_stage,
            location_name=payload.location_name,
            latitude=payload.latitude,
            longitude=payload.longitude,
            observer_role=payload.observer_role,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = await mcp_client.record_farm_observation(
        crop=payload.crop,
        notes=payload.notes,
        growth_stage=parsed_stage.value if parsed_stage else None,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        observer_role=payload.observer_role,
    )
    if result.get("status") != "success":
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to save observation"))
    return result


@router.post("/metrics/calculate")
async def calculate_metrics(payload: AgronomicCalcRequest, request: Request) -> Dict[str, Any]:
    """Compute deterministic GDD and precipitation summaries from daily weather."""
    mcp_client = _get_mcp_client(request)
    result = await mcp_client.calculate_agronomic_metrics(
        daily_weather=payload.daily_weather,
        base_temperature_c=payload.base_temperature_c,
        upper_cutoff_c=payload.upper_cutoff_c,
        dry_day_threshold_mm=payload.dry_day_threshold_mm,
    )
    return result
