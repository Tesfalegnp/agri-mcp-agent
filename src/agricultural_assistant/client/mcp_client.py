"""Custom Model Context Protocol (MCP) Client for the Agricultural Assistant.

Communicates with the Agricultural MCP Server over the standard input/output
(stdio) transport using the official MCP Python SDK.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import Tool

logger = logging.getLogger("agricultural_assistant.client")


class AgriculturalMCPClient:
    """Client for interacting with the Agricultural MCP Server."""

    def __init__(
        self,
        server_command: Optional[str] = None,
        server_args: Optional[List[str]] = None,
        server_env: Optional[Dict[str, str]] = None,
    ) -> None:
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
        self._session_context = None

    async def connect(self) -> ClientSession:
        """Initialize and start the stdio connection with the MCP server.

        Returns:
            Active ClientSession.

        Raises:
            ConnectionError: If unable to spawn server or complete protocol handshake.
        """
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
            logger.info("Connected to MCP Server: %s (version: %s)", init_result.server_info.name, init_result.server_info.version)
            return self._session

        except FileNotFoundError as exc:
            await self.close()
            raise ConnectionError(
                f"Failed to find executable '{self.server_command}'. Ensure 'uv' or Python is installed."
            ) from exc
        except Exception as exc:
            await self.close()
            raise ConnectionError(
                f"Failed to connect to Agricultural MCP Server: {exc}"
            ) from exc

    async def close(self) -> None:
        """Cleanly close the MCP session and terminate the server subprocess."""
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

    async def __aenter__(self) -> AgriculturalMCPClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def session(self) -> ClientSession:
        """Get the active session or raise ConnectionError."""
        if self._session is None:
            raise ConnectionError("MCP Client is not connected. Call connect() first.")
        return self._session

    async def list_tools(self) -> List[Tool]:
        """Discover and return all registered tools from the MCP server."""
        result = await self.session.list_tools()
        return result.tools

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
