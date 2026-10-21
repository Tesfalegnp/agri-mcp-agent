"""Custom Model Context Protocol (MCP) Client for the Agricultural Assistant.

Communicates with the Agricultural MCP Server over:
1. Standard input/output (stdio) transport for local subprocess execution.
2. Streamable HTTP transport for remote client-server connections with OAuth 2.1 authorization.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from typing import Any, Dict, List, Literal, Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import mcp.client.streamable_http as streamable_http_module
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Prompt, Resource, Tool

logger = logging.getLogger("agricultural_assistant.client")


class AgriculturalMCPClient:
    """Client for interacting with the Agricultural MCP Server over stdio or Streamable HTTP."""

    def __init__(
        self,
        transport: Literal["stdio", "streamable-http"] = "stdio",
        server_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        server_command: Optional[str] = None,
        server_args: Optional[List[str]] = None,
        server_env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> None:
        self.transport = transport
        self.server_url = server_url or "http://127.0.0.1:8000/mcp"
        self.bearer_token = bearer_token
        self.timeout = timeout

        # Default to launching through uv if available, or direct python module
        if server_command is None:
            if shutil.which("uv"):
                self.server_command = "uv"
                self.server_args = ["run", "agricultural-assistant-server"]
            else:
                self.server_command = sys.executable
                self.server_args = ["-m", "agricultural_assistant.server.app"]
        else:
            self.server_command = server_command
            self.server_args = server_args or []

        self.server_env = server_env
        self._session: Optional[ClientSession] = None
        self._stdio_context = None
        self._http_context = None
        self._http_client = None
        self._session_context = None
        self._connected_at: Optional[float] = None
        self._last_error: Optional[str] = None
        self._cached_tools: List[Tool] = []

    async def connect(self) -> ClientSession:
        """Initialize and start the connection with the MCP server over configured transport.

        Returns:
            Active ClientSession.

        Raises:
            ConnectionError: If unable to spawn server or complete protocol handshake.
        """
        # Clean up any existing connection first
        await self.close()

        if self.transport == "stdio":
            return await self._connect_stdio()
        elif self.transport == "streamable-http":
            return await self._connect_streamable_http()
        else:
            raise ValueError(f"Unsupported MCP transport: '{self.transport}'")

    async def _connect_stdio(self) -> ClientSession:
        """Connect to MCP server via local stdio subprocess."""
        params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
            env=self.server_env,
        )

        try:
            self._stdio_context = stdio_client(params)
            read_stream, write_stream = await self._stdio_context.__aenter__()

            self._session_context = ClientSession(read_stream, write_stream)
            self._session = await self._session_context.__aenter__()

            init_result = await self._session.initialize()
            self._connected_at = time.time()
            self._last_error = None
            logger.info(
                "Connected to MCP Server via stdio: %s (version: %s)",
                init_result.server_info.name,
                init_result.server_info.version,
            )
            return self._session

        except FileNotFoundError as exc:
            self._last_error = str(exc)
            await self.close()
            raise ConnectionError(
                f"Failed to find executable '{self.server_command}'. Ensure 'uv' or Python is installed."
            ) from exc
        except Exception as exc:
            self._last_error = str(exc)
            await self.close()
            raise ConnectionError(
                f"Failed to connect to Agricultural MCP Server via stdio: {exc}"
            ) from exc

    async def _connect_streamable_http(self) -> ClientSession:
        """Connect to MCP server via Streamable HTTP with optional OAuth token."""
        headers: Dict[str, str] = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        try:
            # Use httpx2 client compatible with mcp.client.streamable_http
            self._http_client = streamable_http_module.httpx2.AsyncClient(
                headers=headers,
                timeout=self.timeout,
            )
            http_ctx = streamable_http_client(
                self.server_url,
                http_client=self._http_client,
            )
            read_stream, write_stream = await http_ctx.__aenter__()
            self._http_context = http_ctx

            session_ctx = ClientSession(read_stream, write_stream)
            self._session = await session_ctx.__aenter__()
            self._session_context = session_ctx

            init_result = await self._session.initialize()
            self._connected_at = time.time()
            self._last_error = None
            logger.info(
                "Connected to MCP Server via Streamable HTTP at %s: %s (version: %s)",
                self.server_url,
                init_result.server_info.name,
                init_result.server_info.version,
            )
            return self._session

        except Exception as exc:
            self._last_error = str(exc)
            await self.close()
            raise ConnectionError(
                f"Failed to connect to Agricultural MCP Server via Streamable HTTP at {self.server_url}: {exc}"
            ) from exc

    async def close(self) -> None:
        """Cleanly close the MCP session and terminate transport resources."""
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("Error closing session: %s", exc)
            self._session_context = None
            self._session = None

        if self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("Error closing stdio transport: %s", exc)
            self._stdio_context = None

        if self._http_context:
            try:
                await self._http_context.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("Error closing Streamable HTTP transport: %s", exc)
            self._http_context = None

        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception as exc:
                logger.debug("Error closing HTTP client: %s", exc)
            self._http_client = None

        self._connected_at = None

    async def __aenter__(self) -> AgriculturalMCPClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def is_connected(self) -> bool:
        """Return True if an active ClientSession exists."""
        return self._session is not None

    @property
    def session(self) -> ClientSession:
        """Get the active session or raise ConnectionError."""
        if self._session is None:
            raise ConnectionError("MCP Client is not connected. Call connect() first.")
        return self._session

    def get_status(self) -> Dict[str, Any]:
        """Return snapshot diagnostics of current connection and transport."""
        return {
            "transport": self.transport,
            "is_connected": self.is_connected,
            "server_url": self.server_url if self.transport == "streamable-http" else None,
            "subprocess_command": f"{self.server_command} {' '.join(self.server_args)}" if self.transport == "stdio" else None,
            "has_bearer_token": bool(self.bearer_token),
            "connected_at": self._connected_at,
            "last_error": self._last_error,
            "cached_tools_count": len(self._cached_tools),
        }

    async def list_tools(self) -> List[Tool]:
        """Discover and return all registered tools from the MCP server."""
        result = await self.session.list_tools()
        self._cached_tools = list(result.tools)
        return self._cached_tools

    async def list_resources(self) -> List[Resource]:
        """Discover and return all registered resources from the MCP server."""
        result = await self.session.list_resources()
        return list(result.resources)

    async def read_resource(self, uri: str) -> Any:
        """Read content from an MCP resource by URI."""
        result = await self.session.read_resource(uri)
        return result

    async def list_prompts(self) -> List[Prompt]:
        """Discover and return all registered prompts from the MCP server."""
        result = await self.session.list_prompts()
        return list(result.prompts)

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, str]] = None) -> Any:
        """Retrieve a formatted prompt template from the MCP server."""
        result = await self.session.get_prompt(name, arguments=arguments)
        return result

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically invoke any registered MCP tool by name."""
        return await self._call_and_parse_tool(tool_name, arguments)

    async def search_crop_disease(
        self,
        crop_name: str,
        symptoms: str,
        growth_stage: Optional[str] = None,
        location_context: Optional[str] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Invoke the search_crop_disease tool over MCP."""
        args: Dict[str, Any] = {
            "crop_name": crop_name,
            "symptoms": symptoms,
            "language": language,
        }
        if growth_stage:
            args["growth_stage"] = growth_stage
        if location_context:
            args["location_context"] = location_context

        return await self._call_and_parse_tool("search_crop_disease", args)

    async def get_weather_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 3,
        crop_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke the get_weather_forecast tool over MCP."""
        args: Dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": forecast_days,
        }
        if crop_context:
            args["crop_context"] = crop_context

        return await self._call_and_parse_tool("get_weather_forecast", args)

    async def record_farm_observation(
        self,
        crop: str,
        notes: str,
        growth_stage: Optional[str] = None,
        observed_at: Optional[str] = None,
        location_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        observer_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke the record_farm_observation tool over MCP."""
        args: Dict[str, Any] = {"crop": crop, "notes": notes}
        if growth_stage:
            args["growth_stage"] = growth_stage
        if observed_at:
            args["observed_at"] = observed_at
        if location_name:
            args["location_name"] = location_name
        if latitude is not None and longitude is not None:
            args["latitude"] = latitude
            args["longitude"] = longitude
        if observer_role:
            args["observer_role"] = observer_role
        return await self._call_and_parse_tool("record_farm_observation", args)

    async def get_farm_observation(self, observation_id: int) -> Dict[str, Any]:
        """Invoke the get_farm_observation tool over MCP."""
        return await self._call_and_parse_tool(
            "get_farm_observation", {"observation_id": observation_id}
        )

    async def list_farm_observations(
        self,
        crop: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke the list_farm_observations tool over MCP."""
        args: Dict[str, Any] = {"limit": limit, "offset": offset}
        if crop:
            args["crop"] = crop
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self._call_and_parse_tool("list_farm_observations", args)

    async def count_farm_observations(self, crop: Optional[str] = None) -> Dict[str, Any]:
        """Invoke the count_farm_observations tool over MCP."""
        args: Dict[str, Any] = {}
        if crop:
            args["crop"] = crop
        return await self._call_and_parse_tool("count_farm_observations", args)

    async def summarize_farm_observations(
        self,
        crop: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke the summarize_farm_observations tool over MCP."""
        args: Dict[str, Any] = {}
        if crop:
            args["crop"] = crop
        if start_date:
            args["start_date"] = start_date
        if end_date:
            args["end_date"] = end_date
        return await self._call_and_parse_tool("summarize_farm_observations", args)

    async def calculate_agronomic_metrics(
        self,
        daily_weather: List[Dict[str, Any]],
        base_temperature_c: float = 10.0,
        upper_cutoff_c: Optional[float] = None,
        dry_day_threshold_mm: float = 1.0,
    ) -> Dict[str, Any]:
        """Invoke calculate_agronomic_metrics tool over MCP."""
        args: Dict[str, Any] = {
            "daily_weather": daily_weather,
            "base_temperature_c": base_temperature_c,
            "dry_day_threshold_mm": dry_day_threshold_mm,
        }
        if upper_cutoff_c is not None:
            args["upper_cutoff_c"] = upper_cutoff_c
        return await self._call_and_parse_tool("calculate_agronomic_metrics", args)

    async def _call_and_parse_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Internal helper to call a tool and deserialize the JSON response."""
        try:
            call_result = await self.session.call_tool(tool_name, arguments)
            if call_result.is_error:
                return {
                    "status": "error",
                    "error_type": "mcp_tool_error",
                    "message": "Tool execution indicated error.",
                    "details": [getattr(c, "text", str(c)) for c in call_result.content],
                }

            if not call_result.content:
                return {
                    "status": "error",
                    "error_type": "empty_content",
                    "message": "Server returned empty tool content.",
                }

            first_content = call_result.content[0]
            content_text = getattr(first_content, "text", "")
            try:
                return json.loads(content_text)
            except json.JSONDecodeError:
                return {
                    "status": "success",
                    "raw_text": content_text,
                }

        except Exception as exc:
            logger.error("MCP tool call error (%s): %s", tool_name, exc)
            return {
                "status": "error",
                "error_type": "mcp_protocol_error",
                "message": f"Protocol error during '{tool_name}' call: {exc}",
            }
