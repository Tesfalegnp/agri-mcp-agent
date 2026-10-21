"""FastAPI routes for the Agricultural MCP Assistant HTTP backend.

Provides:
- End-to-End AI chat with conversational multi-turn gathering and tool execution.
- Real-time Server-Sent Events (SSE) streaming for live UI progress timeline.
- Dual MCP transport selection (stdio vs Streamable HTTP) and diagnostics.
- OAuth 2.1 authorization server, token issuance, PKCE, introspection, and demo credentials.
- Discovered MCP Primitives inspector (Tools, Resources, and Prompts).
- Domain endpoints for localized weather, crop disease pathology, and farm observations.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agricultural_assistant.client.gemini_adapter import GeminiAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import get_settings
from agricultural_assistant.client.orchestrator import (
    ConversationOrchestrator,
    ExecutionActivityEvent,
    orchestrator,
)
from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery
from agricultural_assistant.domain.observation import FarmObservation
from agricultural_assistant.domain.weather import WeatherForecastRequest
from agricultural_assistant.server.oauth import oauth_manager, RegisteredClient

logger = logging.getLogger("agricultural_assistant.api")

router = APIRouter(prefix="/api")


# --- Request & Response Models ---

class ChatRequest(BaseModel):
    """Payload for submitting a question to the AI assistant."""
    prompt: str = Field(..., min_length=1, description="Farmer natural language query")
    conversation_id: Optional[str] = Field(
        default=None, description="Optional conversation session ID for multi-turn tracking"
    )
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Prior conversation turns [{'role': 'user'|'model', 'text': '...'}]"
    )
    auto_confirm_writes: bool = Field(
        default=False, description="If True, auto-approves write operations (e.g. from headless tests)"
    )


class TransportSwitchRequest(BaseModel):
    """Payload for dynamically switching between stdio and Streamable HTTP transports."""
    transport: Literal["stdio", "streamable-http"] = Field(..., description="Target MCP transport")
    server_url: Optional[str] = Field(default=None, description="Server URL for Streamable HTTP")
    bearer_token: Optional[str] = Field(default=None, description="Optional Bearer token for Streamable HTTP")


class OAuthTokenRequest(BaseModel):
    """Payload for exchanging grant code or client credentials for access tokens."""
    grant_type: str = Field(..., description="Grant type: 'authorization_code' or 'client_credentials'")
    client_id: str = Field(..., description="Registered OAuth 2.1 client identifier")
    client_secret: Optional[str] = Field(default=None, description="Client secret for confidential clients")
    code: Optional[str] = Field(default=None, description="Authorization code for code grant")
    code_verifier: Optional[str] = Field(default=None, description="PKCE code verifier")
    redirect_uri: Optional[str] = Field(default=None, description="Registered redirect URI")
    scope: Optional[str] = Field(default="agri:read", description="Requested space-delimited scopes")


class OAuthAuthorizeRequest(BaseModel):
    """Payload for generating an authorization code with PKCE."""
    client_id: str = Field(..., description="Registered OAuth 2.1 client identifier")
    redirect_uri: str = Field(..., description="Registered redirect URI")
    scope: str = Field(default="agri:read agri:write", description="Requested scopes")
    code_challenge: str = Field(..., description="PKCE code challenge (RFC 7636)")
    code_challenge_method: str = Field(default="S256", description="PKCE method (S256 or plain)")


class OAuthIntrospectRequest(BaseModel):
    """Payload for introspecting a token."""
    token: str = Field(..., description="The access token to introspect")


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


def _get_gemini_adapter(request: Request) -> Optional[GeminiAdapter]:
    """Retrieve GeminiAdapter from app state if configured."""
    return getattr(request.app.state, "gemini_adapter", None)


# --- Health & Diagnostic Endpoints ---

@router.get("/health")
async def get_health(request: Request) -> Dict[str, Any]:
    """Return backend, database, and MCP server health status."""
    mcp_client = getattr(request.app.state, "mcp_client", None)
    is_connected = bool(mcp_client and getattr(mcp_client, "_session", None) is not None)
    tool_count = 0
    transport_name = "unknown"

    if mcp_client:
        transport_name = getattr(mcp_client, "transport", "stdio")
        if is_connected:
            try:
                tools = await mcp_client.list_tools()
                tool_count = len(tools)
            except Exception:
                is_connected = False

    return {
        "status": "healthy" if is_connected else "degraded",
        "mcp_server_connected": is_connected,
        "transport": transport_name,
        "tools_discovered": tool_count,
        "service": "Agricultural MCP Assistant",
        "version": "0.1.0",
    }


# --- Conversational Agent Endpoints ---

@router.post("/chat")
async def chat_with_assistant(payload: ChatRequest, request: Request) -> Dict[str, Any]:
    """Submit a natural-language query to the Conversational Agent Orchestrator."""
    mcp_client = _get_mcp_client(request)
    adapter = _get_gemini_adapter(request)

    result = await orchestrator.process_user_turn(
        prompt=payload.prompt,
        conversation_id=payload.conversation_id,
        mcp_client=mcp_client,
        auto_confirm_writes=payload.auto_confirm_writes,
        gemini_adapter=adapter,
    )
    return result


@router.get("/chat/stream")
@router.post("/chat/stream")
async def stream_chat_events(
    request: Request,
    prompt: Optional[str] = Query(default=None),
    conversation_id: Optional[str] = Query(default=None),
    auto_confirm_writes: bool = Query(default=False),
) -> StreamingResponse:
    """Stream genuine real-time execution activity events using Server-Sent Events (SSE)."""
    # Accept prompt from body if POST
    user_prompt = prompt
    target_conv_id = conversation_id
    auto_confirm = auto_confirm_writes

    if request.method == "POST":
        try:
            body = await request.json()
            user_prompt = body.get("prompt") or user_prompt
            target_conv_id = body.get("conversation_id") or target_conv_id
            auto_confirm = body.get("auto_confirm_writes", auto_confirm)
        except Exception:
            pass

    if not user_prompt:
        raise HTTPException(status_code=400, detail="Missing required 'prompt' parameter")

    mcp_client = _get_mcp_client(request)
    adapter = _get_gemini_adapter(request)
    event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    def on_event(event: ExecutionActivityEvent) -> None:
        event_queue.put_nowait({"type": "progress", "data": event.to_dict()})

    async def event_generator() -> AsyncIterator[str]:
        # Task that runs orchestrator turn in background while pushing events
        turn_task = asyncio.create_task(
            orchestrator.process_user_turn(
                prompt=user_prompt,
                conversation_id=target_conv_id,
                mcp_client=mcp_client,
                auto_confirm_writes=auto_confirm,
                event_callback=on_event,
                gemini_adapter=adapter,
            )
        )

        while not turn_task.done() or not event_queue.empty():
            try:
                item = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield f"event: {item['type']}\ndata: {json.dumps(item['data'])}\n\n"
            except asyncio.TimeoutError:
                continue

        # Emit completion payload
        try:
            result = await turn_task
            yield f"event: done\ndata: {json.dumps(result)}\n\n"
        except Exception as exc:
            err_data = {"status": "error", "message": str(exc)}
            yield f"event: error\ndata: {json.dumps(err_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Retrieve complete message history, state, and timeline for a conversation."""
    session = orchestrator.get_or_create_session(conversation_id)
    return {
        "status": "success",
        "conversation": session.to_dict(),
    }


@router.delete("/conversations/{conversation_id}")
async def reset_conversation(conversation_id: str) -> Dict[str, Any]:
    """Reset / start a new conversation session."""
    orchestrator.reset_session(conversation_id)
    return {
        "status": "success",
        "message": f"Conversation session '{conversation_id}' has been reset.",
    }


# --- Transport Selection & Diagnostics ---

@router.get("/mcp/status")
async def get_mcp_status(request: Request) -> Dict[str, Any]:
    """Return status and diagnostic metrics for the active MCP transport connection."""
    mcp_client = getattr(request.app.state, "mcp_client", None)
    if not mcp_client:
        return {
            "status": "disconnected",
            "transport": "none",
            "is_connected": False,
        }

    status_data = mcp_client.get_status()
    # Attach live tool list if connected
    if mcp_client.is_connected:
        try:
            tools = await mcp_client.list_tools()
            status_data["tools"] = [
                {"name": t.name, "description": t.description, "parameters": t.input_schema}
                for t in tools
            ]
            status_data["tools_count"] = len(tools)
        except Exception as exc:
            status_data["tool_error"] = str(exc)

    return {
        "status": "connected" if mcp_client.is_connected else "disconnected",
        **status_data,
    }


@router.post("/mcp/transport")
async def switch_transport(payload: TransportSwitchRequest, request: Request) -> Dict[str, Any]:
    """Switch MCP Client connection dynamically between stdio and Streamable HTTP."""
    current_client: Optional[AgriculturalMCPClient] = getattr(request.app.state, "mcp_client", None)
    logger.info("Switching MCP Client transport to '%s' (server_url=%s)...", payload.transport, payload.server_url)

    # Disconnect old client cleanly
    if current_client:
        try:
            await current_client.close()
        except Exception as exc:
            logger.debug("Error closing previous MCP client: %s", exc)

    # Instantiate new client configured for target transport
    new_client = AgriculturalMCPClient(
        transport=payload.transport,
        server_url=payload.server_url or "http://127.0.0.1:8000/mcp",
        bearer_token=payload.bearer_token,
    )

    try:
        await new_client.connect()
        request.app.state.mcp_client = new_client
        tools = await new_client.list_tools()
        return {
            "status": "success",
            "transport": payload.transport,
            "server_url": payload.server_url,
            "is_connected": True,
            "tools_discovered": len(tools),
            "message": f"Successfully connected to MCP Server via {payload.transport}.",
        }
    except Exception as exc:
        request.app.state.mcp_client = new_client
        logger.error("Failed to connect via %s: %s", payload.transport, exc)
        return {
            "status": "error",
            "transport": payload.transport,
            "is_connected": False,
            "tools_discovered": 0,
            "message": f"Failed to connect via {payload.transport}: {exc}",
        }


# --- MCP Primitives Inspector (Tools, Resources, Prompts) ---

@router.get("/mcp/tools")
async def inspect_mcp_tools(request: Request) -> Dict[str, Any]:
    """Discover and return all registered tools and their typed input schemas."""
    mcp_client = _get_mcp_client(request)
    tools = await mcp_client.list_tools()
    return {
        "status": "success",
        "transport": mcp_client.transport,
        "count": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ],
    }


@router.get("/mcp/resources")
async def inspect_mcp_resources(request: Request) -> Dict[str, Any]:
    """Discover and return all registered resources."""
    mcp_client = _get_mcp_client(request)
    try:
        resources = await mcp_client.list_resources()
        return {
            "status": "success",
            "count": len(resources),
            "resources": [
                {
                    "uri": str(r.uri),
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mimeType,
                }
                for r in resources
            ],
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "resources": []}


@router.get("/mcp/resources/read")
async def read_mcp_resource(request: Request, uri: str = Query(..., description="Resource URI")) -> Dict[str, Any]:
    """Read contents of an MCP resource by URI."""
    mcp_client = _get_mcp_client(request)
    try:
        content = await mcp_client.read_resource(uri)
        return {"status": "success", "uri": uri, "content": getattr(content, "contents", str(content))}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not read resource '{uri}': {exc}")


@router.get("/mcp/prompts")
async def inspect_mcp_prompts(request: Request) -> Dict[str, Any]:
    """Discover and return all registered prompt templates."""
    mcp_client = _get_mcp_client(request)
    try:
        prompts = await mcp_client.list_prompts()
        return {
            "status": "success",
            "count": len(prompts),
            "prompts": [
                {
                    "name": p.name,
                    "description": p.description,
                    "arguments": [
                        {"name": arg.name, "description": arg.description, "required": arg.required}
                        for arg in (p.arguments or [])
                    ],
                }
                for p in prompts
            ],
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "prompts": []}


@router.post("/mcp/prompts/get")
async def get_mcp_prompt(
    request: Request,
    prompt_name: str = Query(...),
    crop: Optional[str] = Query(default="Coffee"),
    symptoms: Optional[str] = Query(default="leaf rust spots"),
) -> Dict[str, Any]:
    """Retrieve and format a registered MCP prompt."""
    mcp_client = _get_mcp_client(request)
    try:
        res = await mcp_client.get_prompt(prompt_name, arguments={"crop": crop, "symptoms": symptoms})
        return {
            "status": "success",
            "prompt_name": prompt_name,
            "description": getattr(res, "description", ""),
            "messages": [
                {"role": getattr(m, "role", "user"), "text": getattr(getattr(m, "content", None), "text", str(m))}
                for m in (getattr(res, "messages", []))
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found: {exc}")


# --- OAuth 2.1 Endpoints ---

@router.get("/oauth/metadata")
@router.get("/.well-known/oauth-authorization-server")
async def get_oauth_metadata() -> Dict[str, Any]:
    """RFC 8414 Authorization Server Metadata."""
    return oauth_manager.get_metadata()


@router.post("/oauth/authorize")
async def oauth_authorize(payload: OAuthAuthorizeRequest) -> Dict[str, Any]:
    """Issue a PKCE authorization code for registered public/confidential clients."""
    try:
        code = oauth_manager.create_authorization_code(
            client_id=payload.client_id,
            redirect_uri=payload.redirect_uri,
            scope=payload.scope,
            code_challenge=payload.code_challenge,
            code_challenge_method=payload.code_challenge_method,
        )
        return {
            "status": "success",
            "code": code,
            "redirect_uri": f"{payload.redirect_uri}?code={code}",
            "expires_in": 600,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/oauth/token")
async def oauth_token(payload: OAuthTokenRequest) -> Dict[str, Any]:
    """Exchange authorization code (PKCE) or client credentials for Bearer access token."""
    try:
        if payload.grant_type == "authorization_code":
            if not payload.code or not payload.code_verifier:
                raise HTTPException(status_code=400, detail="Missing required 'code' or 'code_verifier' for PKCE flow.")
            return oauth_manager.exchange_authorization_code(
                code=payload.code,
                client_id=payload.client_id,
                code_verifier=payload.code_verifier,
                redirect_uri=payload.redirect_uri,
            )
        elif payload.grant_type == "client_credentials":
            if not payload.client_secret:
                raise HTTPException(status_code=400, detail="Missing required 'client_secret' for client_credentials flow.")
            return oauth_manager.exchange_client_credentials(
                client_id=payload.client_id,
                client_secret=payload.client_secret,
                scope=payload.scope,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported grant_type '{payload.grant_type}'. Use 'authorization_code' or 'client_credentials'.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/oauth/introspect")
async def oauth_introspect(payload: OAuthIntrospectRequest) -> Dict[str, Any]:
    """RFC 7662 Token Introspection endpoint."""
    return await oauth_manager.introspect_token(payload.token)


@router.post("/oauth/revoke")
async def oauth_revoke(payload: OAuthIntrospectRequest) -> Dict[str, Any]:
    """RFC 7009 Token Revocation endpoint."""
    revoked = oauth_manager.revoke_token(payload.token)
    return {"status": "success", "revoked": revoked}


@router.get("/oauth/demo-token")
async def get_demo_token(
    request: Request,
    scope: str = Query(default="agri:read agri:write", description="Scopes: 'agri:read', 'agri:write'"),
) -> Dict[str, Any]:
    """Helper endpoint for evaluators to generate verified demonstration tokens.

    Disabled in production mode to prevent unauthorized credential generation.
    """
    settings = getattr(request.app.state, "settings", None) or get_settings()
    if settings.app_env == "production":
        raise HTTPException(
            status_code=403,
            detail="Development demo-token endpoint is disabled in production mode. Use /oauth/token.",
        )

    res = oauth_manager._issue_token_response(
        client_id="agri-evaluator-client",
        scopes=scope.split(),
        subject="evaluator_demo_user",
    )
    return {
        "status": "success",
        "scope": scope,
        "token": res["access_token"],
        "token_type": res["token_type"],
        "expires_in": res["expires_in"],
        "description": f"Verified OAuth 2.1 demonstration token with scopes: {scope}",
    }


# --- Domain Specific Agricultural Endpoints ---

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
