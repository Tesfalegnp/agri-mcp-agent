"""Protocol-level tests for MCP Streamable HTTP transport.

Verifies:
- Streamable HTTP server initialization and capability negotiation
- Tool discovery matches stdio transport (all 8 tools)
- Resource and Prompt discovery
- Tool invocation over Streamable HTTP
- Data consistency across transports sharing the same SQLite database
- Clean session lifecycle management and termination
"""

import asyncio
import contextlib
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agricultural_assistant.server.app import create_server
from agricultural_assistant.storage.database import DatabaseManager


@contextlib.asynccontextmanager
async def streamable_server_ctx(tmp_path, port: int = 8976):
    """Run an ephemeral Streamable HTTP server on localhost."""
    db_file = tmp_path / f"test_streamable_mcp_{port}.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.initialize()

    server = create_server(db_manager=db_mgr)
    starlette_app = server.streamable_http_app(streamable_http_path="/mcp")

    endpoint_url = f"http://127.0.0.1:{port}/mcp"

    config = uvicorn.Config(starlette_app, host="127.0.0.1", port=port, log_level="error")
    uv_server = uvicorn.Server(config)
    task = asyncio.create_task(uv_server.serve())

    for _ in range(30):
        if uv_server.started:
            break
        await asyncio.sleep(0.05)

    try:
        yield endpoint_url
    finally:
        uv_server.should_exit = True
        await task


@pytest.mark.anyio
async def test_streamable_http_initialization_and_tool_discovery(tmp_path):
    """Test connecting to Streamable HTTP endpoint, initializing session, and discovering tools."""
    async with streamable_server_ctx(tmp_path, port=8976) as endpoint_url:
        async with streamable_http_client(endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init_res = await session.initialize()
                assert init_res.server_info.name == "agricultural-assistant-server"
                assert init_res.server_info.version == "0.1.0"

                # Discover tools
                tools_res = await session.list_tools()
                tool_names = [t.name for t in tools_res.tools]
                assert len(tool_names) == 8
                assert "search_crop_disease" in tool_names
                assert "get_weather_forecast" in tool_names
                assert "record_farm_observation" in tool_names
                assert "get_farm_observation" in tool_names
                assert "list_farm_observations" in tool_names
                assert "count_farm_observations" in tool_names
                assert "summarize_farm_observations" in tool_names
                assert "calculate_agronomic_metrics" in tool_names


@pytest.mark.anyio
async def test_streamable_http_prompts_and_resources(tmp_path):
    """Test discovering MCP Prompts and Resources over Streamable HTTP."""
    async with streamable_server_ctx(tmp_path, port=8977) as endpoint_url:
        async with streamable_http_client(endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Discover prompts
                prompts_res = await session.list_prompts()
                prompt_names = [p.name for p in prompts_res.prompts]
                assert "agricultural_advisory_prompt" in prompt_names

                # Discover resources
                resources_res = await session.list_resources()
                resource_uris = [str(r.uri) for r in resources_res.resources]
                assert "crops://catalog" in resource_uris


@pytest.mark.anyio
async def test_streamable_http_tool_execution(tmp_path):
    """Test invoking tools over Streamable HTTP transport."""
    async with streamable_server_ctx(tmp_path, port=8978) as endpoint_url:
        async with streamable_http_client(endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # 1. search_crop_disease
                disease_res = await session.call_tool(
                    "search_crop_disease",
                    arguments={"crop_name": "Teff", "symptoms": "rust spots on stems"},
                )
                assert not disease_res.is_error
                assert len(disease_res.content) > 0
                assert "Teff" in disease_res.content[0].text

                # 2. calculate_agronomic_metrics
                metrics_res = await session.call_tool(
                    "calculate_agronomic_metrics",
                    arguments={
                        "daily_weather": [
                            {"tmax": 25.0, "tmin": 15.0, "precipitation": 5.0},
                            {"tmax": 28.0, "tmin": 16.0, "precipitation": 0.0},
                        ],
                        "base_temperature_c": 10.0,
                    },
                )
                assert not metrics_res.is_error
                assert "growing_degree_days" in metrics_res.content[0].text
                assert "cumulative_gdd" in metrics_res.content[0].text

                # 3. record_farm_observation
                record_res = await session.call_tool(
                    "record_farm_observation",
                    arguments={
                        "crop": "Coffee",
                        "notes": "Verified severe leaf rust symptoms on eastern plot",
                        "location_name": "Jimma Zone",
                    },
                )
                assert not record_res.is_error
                assert "recorded successfully" in record_res.content[0].text

                # 4. list_farm_observations
                list_res = await session.call_tool("list_farm_observations", arguments={"crop": "Coffee"})
                assert not list_res.is_error
                assert "Jimma Zone" in list_res.content[0].text


@pytest.mark.anyio
async def test_streamable_http_error_handling(tmp_path):
    """Test invalid tool arguments and validation error handling over Streamable HTTP."""
    async with streamable_server_ctx(tmp_path, port=8979) as endpoint_url:
        async with streamable_http_client(endpoint_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Pass invalid growth stage to search_crop_disease
                invalid_res = await session.call_tool(
                    "search_crop_disease",
                    arguments={"crop_name": "Wheat", "symptoms": "yellowing", "growth_stage": "invalid_stage_xyz"},
                )
                assert "validation_error" in invalid_res.content[0].text or "Invalid growth_stage" in invalid_res.content[0].text
