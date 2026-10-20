"""OpenAI tool-calling LLM adapter for orchestrating agricultural assistant sessions.

This module provides an adapter for invoking OpenAI models (using the official
OpenAI Python SDK) to coordinate agricultural tools via AgriculturalMCPClient.

Architectural Evaluation:
-------------------------
We evaluated both the OpenAI Responses API and the Chat Completions API.
The Chat Completions API (`client.chat.completions.create`) was chosen as the
primary implementation for Phase 6 for the following reasons:
1. Stability & Standard Compliance: It is the standard, battle-tested tool-calling
   interface across all OpenAI models (including `gpt-4o`, `gpt-4o-mini`, etc.) and
   OpenAI-compatible endpoints.
2. Tool Schema Compatibility: Direct mapping from MCP JSON Schema definitions
   to OpenAI function tool parameters.
3. Multi-turn cycle control: Complete deterministic control over tool call IDs,
   intermediate tool results, multi-tool executions, and maximum execution rounds.
4. Security & Safety: Allows intercepting write operations (e.g. `record_farm_observation`)
   for explicit user authorization prior to reaching the MCP server.

Execution Flow:
---------------
User -> CLI -> LLMAdapter (OpenAI API) -> AgriculturalMCPClient -> AgriculturalMCPServer
     -> Domain Services / SQLite Data -> MCP Server -> MCP Client -> LLMAdapter -> User
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

import openai
from openai import AsyncOpenAI
from mcp.types import Tool

from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import get_settings

logger = logging.getLogger("agricultural_assistant.llm_adapter")

# Default system prompt enforcing evidence-based agricultural decision support
AGRICULTURAL_SYSTEM_PROMPT = (
    "You are an expert Agricultural Assistant helping smallholders, farmers, "
    "and extension agents with crop disease management, localized weather forecasting, "
    "and field observation records.\n\n"
    "Core Guidelines:\n"
    "1. Always use the provided MCP tools to search disease data, retrieve weather forecasts, "
    "query observations, and compute agronomic indices. Do NOT invent data.\n"
    "2. Clearly distinguish between observed facts, database records, weather forecasts, "
    "and possible interpretations.\n"
    "3. Preserve all source references returned by agricultural knowledge tools.\n"
    "4. Explain uncertainty and missing information honestly. Avoid presenting keyword matches "
    "as confirmed diagnoses.\n"
    "5. Avoid inventing pesticide doses, chemical recommendations, or cultivar-specific thresholds.\n"
    "6. Recommend physical inspection by a qualified local extension officer or agronomist "
    "whenever evidence is insufficient or uncertain.\n"
    "7. Never claim that data was retrieved, saved, or verified unless the corresponding operation "
    "actually succeeded.\n"
    "8. If an operation is cancelled or fails, clearly explain the limitation to the user."
)

WRITE_TOOLS = {"record_farm_observation"}


def convert_mcp_tool_to_openai(tool: Tool) -> Dict[str, Any]:
    """Convert an MCP Tool definition to OpenAI function tool schema.

    Preserves tool names, descriptions, parameter types, required fields,
    and optional fields.
    """
    parameters = dict(tool.input_schema) if tool.input_schema else {"type": "object", "properties": {}}
    if "type" not in parameters:
        parameters["type"] = "object"
    if "properties" not in parameters:
        parameters["properties"] = {}

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": parameters,
        },
    }


class LLMAdapter:
    """Adapter for orchestrating OpenAI tool-calling loops with AgriculturalMCPClient."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tool_iterations: Optional[int] = None,
        openai_client: Optional[AsyncOpenAI] = None,
    ) -> None:
        settings = get_settings()

        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self.model = model or settings.openai_model
        self.timeout = timeout if timeout is not None else settings.openai_timeout_seconds
        self.max_tool_iterations = (
            max_tool_iterations if max_tool_iterations is not None else settings.max_tool_rounds
        )

        if openai_client is not None:
            self._client = openai_client
        elif self.api_key:
            client_kwargs: Dict[str, Any] = {
                "api_key": self.api_key,
                "timeout": self.timeout,
            }
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**client_kwargs)
        else:
            self._client = None

    @property
    def client(self) -> Optional[AsyncOpenAI]:
        """Return the underlying AsyncOpenAI client instance."""
        return self._client

    def is_available(self) -> bool:
        """Check whether valid OpenAI credentials are configured."""
        return bool(self.api_key and self.api_key.strip() and self._client is not None)

    async def run_prompt(
        self,
        user_prompt: str,
        mcp_client: AgriculturalMCPClient,
        confirm_write_callback: Optional[
            Callable[[str, Dict[str, Any]], Union[bool, Awaitable[bool]]]
        ] = None,
        auto_confirm_writes: bool = False,
    ) -> Dict[str, Any]:
        """Run the complete agent tool-calling loop against the connected MCP client.

        Args:
            user_prompt: Natural language question from farmer/agronomist.
            mcp_client: Connected AgriculturalMCPClient communicating with MCP server.
            confirm_write_callback: Optional async or sync callable for write confirmation.
            auto_confirm_writes: If True, bypass confirmation (used for headless testing).

        Returns:
            Dictionary containing final response, execution status, and tool invocation log.
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "message": (
                    "No OpenAI API key configured. Set OPENAI_API_KEY in your .env file "
                    "to enable natural-language AI assistant queries. "
                    "You can continue using the direct menu options for deterministic operation."
                ),
                "tool_calls_executed": [],
            }

        # 1. Dynamically discover all tools exposed by the MCP server
        try:
            mcp_tools = await mcp_client.list_tools()
        except Exception as exc:
            logger.error("Failed to discover MCP tools: %s", exc)
            return {
                "status": "error",
                "error_type": "mcp_discovery_failure",
                "message": f"Could not list tools from MCP server: {exc}",
                "tool_calls_executed": [],
            }

        openai_tools = [convert_mcp_tool_to_openai(t) for t in mcp_tools]
        tool_names = {t.name for t in mcp_tools}

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": AGRICULTURAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        tool_execution_log: List[Dict[str, Any]] = []

        # 2. Execute model/tool cycles up to configured safety limit
        for iteration in range(self.max_tool_iterations):
            logger.debug("Starting tool-calling round %d/%d", iteration + 1, self.max_tool_iterations)
            try:
                assert self._client is not None
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    tool_choice="auto" if openai_tools else None,
                )
            except openai.APITimeoutError as exc:
                logger.error("OpenAI timeout error: %s", exc)
                return {
                    "status": "error",
                    "error_type": "openai_timeout_error",
                    "message": f"OpenAI API request timed out: {exc}",
                    "tool_calls_executed": tool_execution_log,
                }
            except openai.APIConnectionError as exc:
                logger.error("OpenAI connection error: %s", exc)
                return {
                    "status": "error",
                    "error_type": "openai_connection_error",
                    "message": f"Network connection to OpenAI API failed: {exc}",
                    "tool_calls_executed": tool_execution_log,
                }
            except openai.APIStatusError as exc:
                logger.error("OpenAI status error (%s): %s", exc.status_code, exc)
                return {
                    "status": "error",
                    "error_type": "openai_status_error",
                    "status_code": exc.status_code,
                    "message": f"OpenAI API returned error: {exc.message}",
                    "tool_calls_executed": tool_execution_log,
                }
            except Exception as exc:
                logger.error("Unexpected OpenAI API failure: %s", exc)
                return {
                    "status": "error",
                    "error_type": "openai_error",
                    "message": f"OpenAI request failed: {exc}",
                    "tool_calls_executed": tool_execution_log,
                }

            choice = response.choices[0]
            message = choice.message

            # If model returned no tool calls, it has produced its final answer
            if not message.tool_calls:
                return {
                    "status": "success",
                    "response_type": "final_answer",
                    "llm_response": message.content or "",
                    "tool_calls_executed": tool_execution_log,
                    "rounds_used": iteration + 1,
                }

            # Serialize model response with tool calls into message history
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
            messages.append(assistant_msg)

            # 3. Process each tool call requested by the model
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments

                # Parse JSON arguments safely
                try:
                    parsed_args = json.loads(raw_args) if raw_args else {}
                    if not isinstance(parsed_args, dict):
                        parsed_args = {}
                except json.JSONDecodeError:
                    tool_result = {
                        "status": "error",
                        "error_type": "malformed_json_arguments",
                        "message": f"Arguments could not be parsed as valid JSON: '{raw_args}'",
                    }
                    tool_execution_log.append(
                        {
                            "tool_name": fn_name,
                            "arguments": raw_args,
                            "result": tool_result,
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result),
                        }
                    )
                    continue

                # Validate tool is actually discovered from the MCP server
                if fn_name not in tool_names:
                    tool_result = {
                        "status": "error",
                        "error_type": "unknown_tool",
                        "message": f"Tool '{fn_name}' is not registered on the MCP server.",
                    }
                    tool_execution_log.append(
                        {
                            "tool_name": fn_name,
                            "arguments": parsed_args,
                            "result": tool_result,
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result),
                        }
                    )
                    continue

                # Write safety check: Confirm before executing write tools
                if fn_name in WRITE_TOOLS:
                    confirmed = False
                    if auto_confirm_writes:
                        confirmed = True
                    elif confirm_write_callback is not None:
                        try:
                            cb_res = confirm_write_callback(fn_name, parsed_args)
                            if inspect.isawaitable(cb_res):
                                confirmed = bool(await cb_res)
                            else:
                                confirmed = bool(cb_res)
                        except Exception as cb_err:
                            logger.warning("Confirmation callback error: %s", cb_err)
                            confirmed = False

                    if not confirmed:
                        tool_result = {
                            "status": "cancelled",
                            "error_type": "user_cancelled_write",
                            "message": (
                                f"Write operation '{fn_name}' was not confirmed by the user. "
                                "The observation was NOT saved to the database."
                            ),
                        }
                        tool_execution_log.append(
                            {
                                "tool_name": fn_name,
                                "arguments": parsed_args,
                                "result": tool_result,
                                "cancelled": True,
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(tool_result),
                            }
                        )
                        continue

                # Execute tool via MCP client (routes to MCP server)
                logger.info("Executing MCP tool '%s' with args %s", fn_name, parsed_args)
                try:
                    if hasattr(mcp_client, fn_name):
                        tool_fn = getattr(mcp_client, fn_name)
                        tool_result = await tool_fn(**parsed_args)
                    else:
                        tool_result = await mcp_client.call_tool(fn_name, parsed_args)
                except Exception as exc:
                    logger.error("Error executing MCP tool '%s': %s", fn_name, exc)
                    tool_result = {
                        "status": "error",
                        "error_type": "mcp_tool_execution_error",
                        "message": f"Failed to execute MCP tool '{fn_name}': {exc}",
                    }

                tool_execution_log.append(
                    {
                        "tool_name": fn_name,
                        "arguments": parsed_args,
                        "result": tool_result,
                    }
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    }
                )

        # Safety limit reached without final response
        return {
            "status": "max_iterations_reached",
            "message": (
                f"Assistant reached the maximum allowed tool-call rounds ({self.max_tool_iterations}) "
                "before producing a final answer."
            ),
            "tool_calls_executed": tool_execution_log,
            "rounds_used": self.max_tool_iterations,
        }
