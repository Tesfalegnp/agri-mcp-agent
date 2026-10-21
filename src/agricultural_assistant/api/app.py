"""FastAPI application factory and lifecycle manager for Agricultural MCP Assistant."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware

from agricultural_assistant.api.routes import router
from agricultural_assistant.client.gemini_adapter import GeminiAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings, get_settings
from agricultural_assistant.logging_config import configure_logging
from agricultural_assistant.server.app import create_server
from agricultural_assistant.server.oauth import oauth_manager

logger = configure_logging()


class OAuthStreamableAuthMiddleware(BaseHTTPMiddleware):
    """Enforce OAuth 2.1 Bearer token authorization for remote Streamable HTTP access at /mcp."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Only enforce on /mcp endpoints
        if path == "/mcp" or path.startswith("/mcp/"):
            enforce_oauth = os.getenv("OAUTH_ENFORCE_REMOTE", "true").lower() in ("true", "1", "yes")
            if enforce_oauth:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.lower().startswith("bearer "):
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": "invalid_token",
                            "error_description": "Authentication required. Remote Streamable HTTP MCP access requires an OAuth 2.1 Bearer token.",
                        },
                        headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="Authentication required"'},
                    )

                token = auth_header[7:].strip()
                verified = await oauth_manager.verify_token(token)
                if not verified:
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": "invalid_token",
                            "error_description": "Invalid, expired, or revoked access token.",
                        },
                        headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="Invalid or expired access token"'},
                    )

                # Scope check: Must contain at least agri:read
                if "agri:read" not in verified.scopes and "agri:write" not in verified.scopes:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "insufficient_scope",
                            "error_description": "Token lacks required 'agri:read' or 'agri:write' scope.",
                        },
                        headers={"WWW-Authenticate": 'Bearer error="insufficient_scope", error_description="Required scope: agri:read"'},
                    )

                # Write operation scope check: tools/call for record_farm_observation requires agri:write
                if request.method == "POST":
                    body_bytes = await request.body()
                    try:
                        body_json = json.loads(body_bytes.decode("utf-8"))
                        if isinstance(body_json, dict) and body_json.get("method") == "tools/call":
                            params = body_json.get("params", {})
                            tool_name = params.get("name") if isinstance(params, dict) else None
                            if tool_name == "record_farm_observation" and "agri:write" not in verified.scopes:
                                return JSONResponse(
                                    status_code=403,
                                    content={
                                        "error": "insufficient_scope",
                                        "error_description": "Write tool 'record_farm_observation' requires 'agri:write' scope.",
                                    },
                                    headers={"WWW-Authenticate": 'Bearer error="insufficient_scope", error_description="Required scope: agri:write"'},
                                )
                    except Exception:
                        pass

                    # Reconstruct request receive stream so downstream handler can read body
                    async def receive():
                        return {"type": "http.request", "body": body_bytes}
                    request = Request(request.scope, receive=receive)

                # Store verified token on request state
                request.state.oauth_token = verified

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle for Web and MCP Streamable HTTP."""
    settings = get_settings()
    logger.info("Initializing Agricultural MCP Services for Web Backend...")

    mcp_server: Optional[MCPServer] = getattr(app.state, "mcp_server", None)
    mcp_client: Optional[AgriculturalMCPClient] = getattr(app.state, "mcp_client", None)
    own_client = False

    async with contextlib.AsyncExitStack() as stack:
        # Start Streamable HTTP MCP session manager if available
        if mcp_server is not None:
            await stack.enter_async_context(mcp_server.session_manager.run())
            logger.info("Streamable HTTP MCP session manager activated at /mcp")

        # Initialize local stdio client for backend API tool calling
        if mcp_client is None:
            mcp_client = AgriculturalMCPClient(transport="stdio")
            own_client = True
            try:
                await mcp_client.connect()
                logger.info("Local MCP Client connected successfully to stdio MCP Server.")
            except Exception as exc:
                logger.warning("Failed to automatically connect local MCP Client at startup: %s", exc)

        app.state.mcp_client = mcp_client
        if not hasattr(app.state, "gemini_adapter") or app.state.gemini_adapter is None:
            app.state.gemini_adapter = GeminiAdapter()

        yield

        if own_client and mcp_client:
            logger.info("Closing local MCP Client connection...")
            try:
                await mcp_client.close()
            except Exception as exc:
                logger.debug("Error while closing local MCP Client: %s", exc)


def create_app(
    settings: Optional[Settings] = None,
    mcp_client: Optional[AgriculturalMCPClient] = None,
    gemini_adapter: Optional[GeminiAdapter] = None,
    mcp_server: Optional[MCPServer] = None,
) -> FastAPI:
    """Create and configure the FastAPI web application instance with Streamable HTTP MCP."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title="Agricultural MCP Assistant API",
        description="REST API and Streamable HTTP MCP server connecting React frontend and MCP clients to Gemini AI, OAuth 2.1, and SQLite persistence.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Initialize app state
    app.state.settings = app_settings
    app.state.mcp_client = mcp_client
    app.state.gemini_adapter = gemini_adapter

    # Mount Streamable HTTP MCP server
    server_instance = mcp_server or create_server()
    app.state.mcp_server = server_instance
    mcp_starlette_app = server_instance.streamable_http_app(streamable_http_path="/")
    app.mount("/mcp", mcp_starlette_app)

    # Add OAuth 2.1 authorization middleware for remote Streamable HTTP
    app.add_middleware(OAuthStreamableAuthMiddleware)

    # Configure CORS for local frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/.well-known/oauth-authorization-server")
    async def root_oauth_metadata() -> JSONResponse:
        """RFC 8414 Authorization Server Metadata at well-known root URI."""
        return JSONResponse(oauth_manager.get_metadata())

    app.include_router(router)

    return app


# Default app instance for standard ASGI servers
app = create_app()


def main() -> None:
    """Run the API server with Uvicorn."""
    import uvicorn

    settings = get_settings()
    print(f"Starting Agricultural Assistant Web Backend on http://{settings.backend_host}:{settings.backend_port}")
    uvicorn.run(
        "agricultural_assistant.api.app:create_app",
        host=settings.backend_host,
        port=settings.backend_port,
        factory=True,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
