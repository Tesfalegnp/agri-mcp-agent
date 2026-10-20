"""End-to-end integration test verifying MCP Client and Server communication over stdio."""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

from agricultural_assistant.client.mcp_client import AgriculturalMCPClient


@pytest.mark.anyio
async def test_end_to_end_mcp_stdio_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify stdio server spawn, tool listing, observation recording, retrieval, and cleanup."""
    import os

    db_file = tmp_path / "e2e_test.db"
    env = dict(os.environ)
    env["DATABASE_PATH"] = str(db_file)

    client = AgriculturalMCPClient(
        server_command=sys.executable,
        server_args=["-m", "agricultural_assistant.server.app"],
        server_env=env,
    )
    try:
        await client.connect()

        # 1. List tools and verify all 8 tools are registered
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        expected_tools = {
            "search_crop_disease",
            "get_weather_forecast",
            "record_farm_observation",
            "get_farm_observation",
            "list_farm_observations",
            "count_farm_observations",
            "summarize_farm_observations",
            "calculate_agronomic_metrics",
        }
        assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"

        # 2. Record an observation via stdio
        record_res = await client.record_farm_observation(
            crop="Teff",
            notes="Observed minor lodging after strong evening rains.",
            growth_stage="maturity",
            location_name="Debre Zeit test plot",
            latitude=8.75,
            longitude=38.98,
            observer_role="researcher",
        )
        assert record_res["status"] == "success", record_res
        obs_id = record_res["observation_id"]
        assert obs_id is not None

        # 3. Retrieve the recorded observation
        get_res = await client.get_farm_observation(obs_id)
        assert get_res["status"] == "success"
        obs = get_res["observation"]
        assert obs["id"] == obs_id
        assert obs["crop"] == "Teff"
        assert "lodging" in obs["notes"]

        # 4. List observations
        list_res = await client.list_farm_observations(crop="teff")
        assert list_res["status"] == "success"
        assert list_res["total_count"] == 1
        assert len(list_res["observations"]) == 1

        # 5. Summarize observations
        summary_res = await client.summarize_farm_observations(crop="teff")
        assert summary_res["status"] == "success"
        assert summary_res["total_observations"] == 1
        assert summary_res["crop_distribution"].get("Teff") == 1

        # 6. Search crop disease (FTS5 backed)
        disease_res = await client.search_crop_disease(
            crop_name="Maize",
            symptoms="caterpillars feeding on leaves whorl damage",
            growth_stage="vegetative",
        )
        assert disease_res["status"] == "success"
        assert len(disease_res["potential_matches"]) >= 1

        # 7. Calculate agronomic metrics
        metrics_res = await client.calculate_agronomic_metrics(
            daily_weather=[
                {"date": "2026-10-01", "max_temp_c": 26.0, "min_temp_c": 12.0, "precipitation_mm": 5.0},
                {"date": "2026-10-02", "max_temp_c": 28.0, "min_temp_c": 14.0, "precipitation_mm": 12.0},
            ],
            base_temperature_c=10.0,
        )
        assert metrics_res["status"] == "success"
        assert metrics_res["growing_degree_days"]["cumulative_gdd"] == 20.0
        assert metrics_res["precipitation_summary"]["cumulative_precipitation_mm"] == 17.0

    finally:
        await client.close()


@pytest.mark.anyio
async def test_end_to_end_ai_mcp_real_server_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify complete User -> AI Assistant -> MCP Client -> Real MCP Server -> SQLite -> User loop."""
    import json
    import os
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from agricultural_assistant.client.llm_adapter import LLMAdapter

    db_file = tmp_path / "ai_e2e_test.db"
    env = dict(os.environ)
    env["DATABASE_PATH"] = str(db_file)

    client = AgriculturalMCPClient(
        server_command=sys.executable,
        server_args=["-m", "agricultural_assistant.server.app"],
        server_env=env,
    )
    try:
        await client.connect()

        # Step 1: Model requests real MCP write tool 'record_farm_observation'
        write_call = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_save_coffee",
                                type="function",
                                function=SimpleNamespace(
                                    name="record_farm_observation",
                                    arguments=json.dumps(
                                        {
                                            "crop": "Coffee",
                                            "notes": "Observed dark sunken lesions on green berries",
                                            "location_name": "Jimma Field 2",
                                        }
                                    ),
                                ),
                            )
                        ],
                    )
                )
            ]
        )

        # Step 2: After write succeeds, model requests 'count_farm_observations'
        count_call = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call_count_coffee",
                                type="function",
                                function=SimpleNamespace(
                                    name="count_farm_observations",
                                    arguments=json.dumps({"crop": "Coffee"}),
                                ),
                            )
                        ],
                    )
                )
            ]
        )

        # Step 3: Model receives real count from SQLite and provides final answer
        final_answer = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        role="assistant",
                        content="Your coffee observation was saved to the database, and there is now 1 coffee observation recorded.",
                        tool_calls=None,
                    )
                )
            ]
        )

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[write_call, count_call, final_answer]
        )

        adapter = LLMAdapter(api_key="mock-key", openai_client=mock_openai)

        # Execute prompt with explicit write confirmation callback
        confirm_callback = MagicMock(return_value=True)
        res = await adapter.run_prompt(
            "Please record a coffee observation with dark sunken lesions on berries, then check the total count.",
            client,
            confirm_write_callback=confirm_callback,
        )

        assert res["status"] == "success"
        assert res["response_type"] == "final_answer"
        assert "1 coffee observation recorded" in res["llm_response"]
        assert len(res["tool_calls_executed"]) == 2

        # Check write tool execution on real server
        save_execution = res["tool_calls_executed"][0]
        assert save_execution["tool_name"] == "record_farm_observation"
        assert save_execution["result"]["status"] == "success"
        obs_id = save_execution["result"]["observation_id"]
        assert obs_id == 1

        # Check count tool execution on real server
        count_execution = res["tool_calls_executed"][1]
        assert count_execution["tool_name"] == "count_farm_observations"
        assert count_execution["result"]["status"] == "success"
        assert count_execution["result"]["count"] == 1

        # Verify real SQLite database actually contains the record
        verify_record = await client.get_farm_observation(obs_id)
        assert verify_record["status"] == "success"
        assert verify_record["observation"]["crop"] == "Coffee"
        assert "dark sunken lesions" in verify_record["observation"]["notes"]

    finally:
        await client.close()
