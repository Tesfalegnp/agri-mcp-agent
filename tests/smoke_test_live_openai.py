"""Optional live smoke test for OpenAI API and MCP integration.

This script executes a live end-to-end request against the real OpenAI API
and the real local Agricultural MCP Server.

To run:
    uv run python tests/smoke_test_live_openai.py

IMPORTANT:
- Never prints, logs, or returns the actual API key.
- Clearly distinguishes between mocked automated tests and live API testing.
- Requires network access and a valid OPENAI_API_KEY in the environment or .env.
"""

from __future__ import annotations

import asyncio
import os
import sys

from agricultural_assistant.client.llm_adapter import LLMAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import get_settings


async def run_live_smoke_test() -> int:
    """Run an end-to-end live smoke test using real OpenAI API and real MCP server."""
    print("=" * 70)
    print("      AGRICULTURAL MCP ASSISTANT — LIVE OPENAI SMOKE TEST")
    print("=" * 70)

    settings = get_settings()
    api_key = settings.openai_api_key

    if not api_key or not api_key.strip():
        print("[SKIPPED] No OPENAI_API_KEY found in environment or .env.")
        print("To run live smoke verification:")
        print("  1. Add OPENAI_API_KEY=sk-... to your local .env file.")
        print("  2. Re-run: uv run python tests/smoke_test_live_openai.py")
        print("Automated test suite (pytest) remains 100% mocked and offline-safe.")
        print("=" * 70)
        return 0

    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    print(f"OpenAI Model Configured: {settings.openai_model}")
    print(f"API Key Detected:        {masked_key} (Redacted for security)")
    print("Connecting to local Agricultural MCP Server (stdio transport)...")

    client = AgriculturalMCPClient(
        server_command=sys.executable,
        server_args=["-m", "agricultural_assistant.server.app"],
    )

    try:
        await client.connect()
        tools = await client.list_tools()
        print(f"Discovered {len(tools)} MCP Tools:")
        for t in tools:
            print(f"  * {t.name}")

        adapter = LLMAdapter()
        test_prompt = (
            "What diseases might cause dark sunken lesions on green coffee berries? "
            "Please check the agricultural knowledge base and summarize the diagnosis."
        )

        print("\nSending live query to OpenAI model:")
        print(f"User Prompt: '{test_prompt}'")
        print("Waiting for model tool-calling cycle...")

        result = await adapter.run_prompt(test_prompt, client)

        print("\n" + "-" * 70)
        print("LIVE EXECUTION RESULT:")
        print(f"Status:        {result.get('status')}")
        print(f"Response Type: {result.get('response_type', 'N/A')}")
        print(f"Rounds Used:   {result.get('rounds_used', 0)}")

        executed = result.get("tool_calls_executed", [])
        print(f"Tools Invoked: {len(executed)}")
        for idx, call in enumerate(executed, start=1):
            print(f"  [{idx}] Tool: '{call['tool_name']}'")
            print(f"      Args:   {call['arguments']}")
            res_preview = str(call["result"])
            if len(res_preview) > 120:
                res_preview = res_preview[:120] + "..."
            print(f"      Result: {res_preview}")

        print("\nFinal Model Answer:")
        print(result.get("llm_response", "(No response)"))
        print("-" * 70)

        if result.get("status") == "success" and len(executed) >= 1:
            print("[LIVE API SMOKE TEST PASSED] Full AI -> MCP Client -> MCP Server -> AI cycle verified.")
            print("=" * 70)
            return 0
        else:
            print(f"[LIVE SMOKE TEST FAILED] Unexpected result: {result.get('message')}")
            print("=" * 70)
            return 1

    except Exception as exc:
        print(f"\n[LIVE SMOKE TEST ERROR]: {exc}")
        print("=" * 70)
        return 1
    finally:
        await client.close()


def main() -> None:
    code = asyncio.run(run_live_smoke_test())
    sys.exit(code)


if __name__ == "__main__":
    main()
