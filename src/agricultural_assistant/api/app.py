"""FastAPI application factory and lifecycle manager for Agricultural MCP Assistant."""

from __future__ import annotations

import logging
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.mcpserver import MCPServer

from agricultural_assistant.api.routes import router
from agricultural_assistant.client.gemini_adapter import GeminiAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import Settings, get_settings
from agricultural_assistant.logging_config import configure_logging
from agricultural_assistant.server.app import create_server

logger = configure_logging()


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
            mcp_client = AgriculturalMCPClient()
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
        description="REST API and Streamable HTTP MCP server connecting React frontend and MCP clients to Gemini AI and SQLite persistence.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Initialize app state
    app.state.mcp_client = mcp_client
    app.state.gemini_adapter = gemini_adapter

    # Mount Streamable HTTP MCP server
    server_instance = mcp_server or create_server()
    app.state.mcp_server = server_instance
    mcp_starlette_app = server_instance.streamable_http_app(streamable_http_path="/")
    app.mount("/mcp", mcp_starlette_app)

    # Configure CORS for local frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


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
