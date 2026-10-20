"""Google Gemini tool-calling AI adapter for orchestrating agricultural assistant sessions.

This module provides an adapter using the official Google GenAI SDK (`google-genai`)
to coordinate agricultural tools via AgriculturalMCPClient.

Execution Flow:
---------------
Farmer -> Web UI / CLI -> GeminiAdapter -> AgriculturalMCPClient -> AgriculturalMCPServer
       -> Domain Services / SQLite Data -> MCP Server -> MCP Client -> GeminiAdapter -> Farmer
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from mcp.types import Tool

from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.config import get_settings

logger = logging.getLogger("agricultural_assistant.gemini_adapter")

# Evidence-based agricultural decision support system prompt
AGRICULTURAL_SYSTEM_PROMPT = (
    "You are an expert Agricultural Assistant helping smallholders, farmers, "
    "and extension agents with crop disease management, localized weather forecasting, "
    "and field observation records.\n\n"
    "Core Guidelines:\n"
    "1. Always use the provided tools to search disease data, retrieve weather forecasts, "
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
    "8. If an operation is cancelled or fails, clearly explain the limitation to the farmer."
)

WRITE_TOOLS = {"record_farm_observation"}


def convert_mcp_tool_to_gemini(tool: Tool) -> types.FunctionDeclaration:
    """Convert an MCP Tool definition to a Gemini FunctionDeclaration.

    Preserves tool names, descriptions, parameter types, required fields,
    and optional fields.
    """
    parameters = dict(tool.input_schema) if tool.input_schema else {"type": "object", "properties": {}}
    if "type" not in parameters:
        parameters["type"] = "object"
    if "properties" not in parameters:
        parameters["properties"] = {}

    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or "",
        parameters=parameters,
    )


class GeminiAdapter:
    """Adapter for orchestrating Google Gemini tool-calling loops with AgriculturalMCPClient."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tool_iterations: Optional[int] = None,
        client: Optional[genai.Client] = None,
    ) -> None:
        settings = get_settings()

        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.timeout = timeout if timeout is not None else settings.openai_timeout_seconds
        self.max_tool_iterations = (
            max_tool_iterations if max_tool_iterations is not None else settings.max_tool_rounds
        )

        if client is not None:
            self._client = client
        elif self.api_key and self.api_key.strip():
            http_options = {"timeout": self.timeout} if self.timeout else None
            self._client = genai.Client(api_key=self.api_key, http_options=http_options)
        else:
            self._client = None

    @property
    def client(self) -> Optional[genai.Client]:
        """Return the underlying genai.Client instance."""
        return self._client

    def is_available(self) -> bool:
        """Check whether valid Gemini credentials are configured."""
        return bool(self.api_key and self.api_key.strip() and self._client is not None)

    async def run_prompt(
        self,
        user_prompt: str,
        mcp_client: AgriculturalMCPClient,
        confirm_write_callback: Optional[
            Callable[[str, Dict[str, Any]], Union[bool, Awaitable[bool]]]
        ] = None,
        auto_confirm_writes: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Run the complete agent tool-calling loop against the connected MCP client.

        Args:
            user_prompt: Natural language question from farmer/agronomist.
            mcp_client: Connected AgriculturalMCPClient communicating with MCP server.
            confirm_write_callback: Optional async or sync callable for write confirmation.
            auto_confirm_writes: If True, bypass confirmation (used for headless testing).
            conversation_history: Optional prior messages in [{"role": "user"|"model", "text": "..."}].

        Returns:
            Dictionary containing final response, execution status, and tool invocation log.
        """
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

        gemini_functions = [convert_mcp_tool_to_gemini(t) for t in mcp_tools]
        tool_names = {t.name for t in mcp_tools}
        tools_config = [types.Tool(function_declarations=gemini_functions)] if gemini_functions else None

        if not self.is_available():
            # Graceful deterministic fallback when no Gemini key is provided
            return await self._fallback_deterministic_execution(
                user_prompt, mcp_client, tool_names, confirm_write_callback, auto_confirm_writes
            )

        # Build contents from history and current prompt
        contents: List[types.Content] = []
        if conversation_history:
            for msg in conversation_history:
                role = "user" if msg.get("role") == "user" else "model"
                text = msg.get("text", "")
                if text:
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]))

        tool_execution_log: List[Dict[str, Any]] = []

        config = types.GenerateContentConfig(
            system_instruction=AGRICULTURAL_SYSTEM_PROMPT,
            tools=tools_config,
            temperature=0.2,
        )

        for iteration in range(self.max_tool_iterations):
            logger.debug("Starting Gemini tool-calling round %d/%d", iteration + 1, self.max_tool_iterations)
            try:
                assert self._client is not None
                # Run synchronous SDK call in thread pool to avoid blocking async event loop
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except genai_errors.APIError as exc:
                logger.error("Gemini API error (%s): %s", exc.code, exc.message)
                error_msg = exc.message or str(exc)
                if exc.code == 429 or "quota" in error_msg.lower():
                    return {
                        "status": "error",
                        "error_type": "gemini_quota_exhausted",
                        "message": (
                            "Gemini API free tier quota exhausted. Please try again in a few moments, "
                            "or use the direct feature tabs (Weather, Diseases, Observations)."
                        ),
                        "tool_calls_executed": tool_execution_log,
                    }
                return {
                    "status": "error",
                    "error_type": "gemini_api_error",
                    "message": f"Gemini API returned error ({exc.code}): {error_msg}",
                    "tool_calls_executed": tool_execution_log,
                }
            except Exception as exc:
                logger.warning("Gemini network or execution exception (%s): %s", type(exc).__name__, exc)
                # If network is unreachable or offline, provide graceful fallback rather than hard crashing
                if "network is unreachable" in str(exc).lower() or "connecterror" in str(exc).lower():
                    logger.info("Network unreachable; activating deterministic offline assistant fallback.")
                    return await self._fallback_deterministic_execution(
                        user_prompt, mcp_client, tool_names, confirm_write_callback, auto_confirm_writes
                    )
                return {
                    "status": "error",
                    "error_type": "gemini_connection_error",
                    "message": f"Failed to communicate with Gemini API: {exc}",
                    "tool_calls_executed": tool_execution_log,
                }

            # Check for candidate and parts
            if not response.candidates:
                return {
                    "status": "error",
                    "error_type": "empty_gemini_response",
                    "message": "Gemini returned no response candidates.",
                    "tool_calls_executed": tool_execution_log,
                }

            candidate = response.candidates[0]
            model_content = candidate.content
            if not model_content or not model_content.parts:
                return {
                    "status": "success",
                    "response_type": "final_answer",
                    "llm_response": response.text or "I processed your request, but have no additional details.",
                    "tool_calls_executed": tool_execution_log,
                    "rounds_used": iteration + 1,
                }

            # Inspect parts for function calls
            function_calls = [p.function_call for p in model_content.parts if p.function_call]

            # If no function calls requested, this is the final answer
            if not function_calls:
                text_parts = [p.text for p in model_content.parts if p.text]
                final_text = "\n".join(text_parts) if text_parts else (response.text or "")
                return {
                    "status": "success",
                    "response_type": "final_answer",
                    "llm_response": final_text,
                    "tool_calls_executed": tool_execution_log,
                    "rounds_used": iteration + 1,
                }

            # Append model's response (with function calls) to conversation history
            contents.append(model_content)

            # Process each requested function call
            response_parts: List[types.Part] = []
            for fc in function_calls:
                fn_name = fc.name
                raw_args = fc.args or {}
                parsed_args = dict(raw_args) if isinstance(raw_args, dict) else {}

                # Unknown tool check
                if fn_name not in tool_names:
                    tool_result = {
                        "status": "error",
                        "error_type": "unknown_tool",
                        "message": f"Tool '{fn_name}' is not registered on the MCP server.",
                    }
                    tool_execution_log.append(
                        {"tool_name": fn_name, "arguments": parsed_args, "result": tool_result}
                    )
                    response_parts.append(
                        types.Part.from_function_response(name=fn_name, response={"result": tool_result})
                    )
                    continue

                # Write-Operation Safety Check
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
                                f"Write operation '{fn_name}' was not confirmed by the farmer. "
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
                        response_parts.append(
                            types.Part.from_function_response(
                                name=fn_name, response={"result": tool_result}
                            )
                        )
                        continue

                # Execute tool via MCP client
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
                    {"tool_name": fn_name, "arguments": parsed_args, "result": tool_result}
                )
                response_parts.append(
                    types.Part.from_function_response(name=fn_name, response={"result": tool_result})
                )

            # Return tool response parts to Gemini in a user-role content message
            contents.append(types.Content(role="user", parts=response_parts))

        # Iteration safety limit reached
        return {
            "status": "max_iterations_reached",
            "message": (
                f"Assistant reached the maximum allowed tool-call rounds ({self.max_tool_iterations}) "
                "before producing a final answer."
            ),
            "tool_calls_executed": tool_execution_log,
            "rounds_used": self.max_tool_iterations,
        }

    async def _fallback_deterministic_execution(
        self,
        prompt: str,
        mcp_client: AgriculturalMCPClient,
        tool_names: set[str],
        confirm_write_callback: Optional[Any],
        auto_confirm_writes: bool,
    ) -> Dict[str, Any]:
        """Deterministic offline intent resolver executing real MCP tools when Gemini is unreachable."""
        prompt_lower = prompt.lower()
        tool_calls_executed: List[Dict[str, Any]] = []

        # Intent 1: Crop Disease Inquiry
        crops = ["coffee", "maize", "teff", "wheat", "sorghum"]
        matched_crop = next((c for c in crops if c in prompt_lower), None)

        if any(w in prompt_lower for w in ["disease", "symptom", "lesion", "rust", "rot", "blight", "caterpillar", "pest", "spots"]) or matched_crop:
            crop_name = matched_crop or "coffee"
            symptoms = prompt
            res = await mcp_client.search_crop_disease(crop_name=crop_name, symptoms=symptoms)
            tool_calls_executed.append({
                "tool_name": "search_crop_disease",
                "arguments": {"crop_name": crop_name, "symptoms": symptoms},
                "result": res,
            })
            matches = res.get("potential_matches", [])
            if matches:
                top = matches[0]
                answer = (
                    f"Based on agricultural research records (EIAR/CABI), your {crop_name} symptoms match **{top.get('disease_name')}** "
                    f"(*{top.get('scientific_name', 'N/A')}*).\n\n"
                    f"**Recommended Management:**\n"
                    + "\n".join(f"- {rec}" for rec in top.get("management_recommendations", []))
                    + f"\n\n*Source:* {top.get('source_reference', 'Agricultural Knowledge Base')}\n\n"
                    f"**Caution:** {res.get('diagnostic_disclaimer', 'Consult a local agronomist for physical inspection.')}"
                )
            else:
                answer = f"No exact disease records found for {crop_name} with these symptoms. Please consult a local agricultural extension officer."

            return {
                "status": "success",
                "response_type": "final_answer",
                "llm_response": answer,
                "tool_calls_executed": tool_calls_executed,
                "rounds_used": 1,
            }

        # Intent 2: Weather Forecast
        if any(w in prompt_lower for w in ["weather", "forecast", "rain", "temperature", "climate"]):
            res = await mcp_client.get_weather_forecast(latitude=9.02, longitude=38.74, forecast_days=3)
            tool_calls_executed.append({
                "tool_name": "get_weather_forecast",
                "arguments": {"latitude": 9.02, "longitude": 38.74, "forecast_days": 3},
                "result": res,
            })
            days = res.get("daily_forecast", [])
            summary_lines = [
                f"- **{d.get('date')}**: Max {d.get('max_temperature_c')}°C, Min {d.get('min_temperature_c')}°C, Rain: {d.get('precipitation_mm')}mm ({d.get('precipitation_probability_pct')}% chance)"
                for d in days
            ]
            answer = (
                f"**Localized Weather Forecast (Addis Ababa - 9.02°N, 38.74°E):**\n"
                + "\n".join(summary_lines)
                + f"\n\n*Attribution:* {res.get('attribution', 'Open-Meteo')}"
            )
            return {
                "status": "success",
                "response_type": "final_answer",
                "llm_response": answer,
                "tool_calls_executed": tool_calls_executed,
                "rounds_used": 1,
            }

        # Intent 3: Observations Count / Summary
        if any(w in prompt_lower for w in ["how many", "count", "number of"]) and "observation" in prompt_lower:
            res = await mcp_client.count_farm_observations(crop=matched_crop)
            tool_calls_executed.append({
                "tool_name": "count_farm_observations",
                "arguments": {"crop": matched_crop},
                "result": res,
            })
            cnt = res.get("count", 0)
            crop_str = f" for {matched_crop}" if matched_crop else ""
            return {
                "status": "success",
                "response_type": "final_answer",
                "llm_response": f"There are currently **{cnt}** farm observation(s) recorded in your SQLite database{crop_str}.",
                "tool_calls_executed": tool_calls_executed,
                "rounds_used": 1,
            }

        if any(w in prompt_lower for w in ["summary", "summarize", "history", "recent"]):
            res = await mcp_client.summarize_farm_observations(crop=matched_crop)
            tool_calls_executed.append({
                "tool_name": "summarize_farm_observations",
                "arguments": {"crop": matched_crop},
                "result": res,
            })
            total = res.get("total_observations", 0)
            dist = res.get("crop_distribution", {})
            dist_str = ", ".join(f"{c}: {n}" for c, n in dist.items()) if dist else "None"
            return {
                "status": "success",
                "response_type": "final_answer",
                "llm_response": (
                    f"**Historical Farm Observations Summary:**\n"
                    f"- Total Records: {total}\n"
                    f"- Crop Distribution: {dist_str}\n"
                    f"- *Confidence Note:* {res.get('confidence_note', '')}"
                ),
                "tool_calls_executed": tool_calls_executed,
                "rounds_used": 1,
            }

        # Default helpful response
        return {
            "status": "success",
            "response_type": "final_answer",
            "llm_response": (
                "Hello! I am your Agricultural Assistant. I can help you with:\n"
                "1. **Crop Disease Identification:** Ask about symptoms (e.g. coffee leaf rust, maize armyworm).\n"
                "2. **Weather Forecasts:** Ask for localized weather by coordinates.\n"
                "3. **Farm Observations:** Inquire about recorded field notes, counts, and historical summaries.\n"
                "4. **Agronomic Calculations:** Compute Growing Degree Days (GDD) and rainfall patterns."
            ),
            "tool_calls_executed": [],
            "rounds_used": 1,
        }
