# Agricultural MCP Assistant — Architecture & Implementation Summary

## 1. Executive Summary & Use Case
The **Agricultural MCP Assistant** is a full-stack, AI-powered agricultural decision-support system designed for smallholder farmers, agricultural extension workers, and agronomists in Eastern Africa (with regional focus on Ethiopia).

### Problem Solved
Smallholder farming communities frequently suffer devastating crop losses because disease symptoms (such as Coffee Leaf Rust, Maize Fall Armyworm, or Teff Leaf Rust) are identified too late, treatments are unverified or hallucinated, and localized weather forecasts are inaccessible. This application connects vetted, research-grounded agricultural knowledge with real-time field observations and localized weather forecasts through the **Model Context Protocol (MCP)** and **Google Gemini tool calling**.

---

## 2. System Architecture & Component Interaction

```
[ Farmer / Extension Agent ]
            |
            v
[ React 18 + Vite Web UI ]  <-- (REST JSON) -->  [ FastAPI Backend (:8000) ]
                                                            |
                 +------------------------------------------+-----------------------+
                 |                                                                  |
                 v                                                                  v
        [ GeminiAdapter ]                                                 [ Direct REST Routes ]
    (google-genai / Gemini 3.5)                                             (/api/health, /api/weather,
                 |                                                          /api/diseases, /api/observations)
                 v (Tool Execution Request)                                         |
     [ AgriculturalMCPClient ]                                                      |
                 | (JSON-RPC stdio)                                                 |
                 v                                                                  |
     [ AgriculturalMCPServer ]  <===================================================+
        * 8 Tools                                             |
        * Resource: crops://catalog                           |
        * Prompt: agricultural_advisory_prompt                |
        * Transports: stdio + Streamable HTTP (/mcp)          |
                 |                                            |
                 +-------------------+------------------------+
                                     |
           +-------------------------+------------------------+
           |                                                  |
           v                                                  v
[ SQLite 3 DB + FTS5 Full-Text Search ]           [ Open-Meteo Cloud Weather API ]
  - Curated EIAR/CABI pathology records             - 1-14 day daily forecasts
  - Persistent farm observations & logs             - Precipitation, temps, rain probability
  - Online hot backup & restore
```

### How the Pieces Fit Together

1. **Resources (External Data & State):**
   - **SQLite Database (`data/agricultural_assistant.db`):** Curated pathology compendium seeded with official Ethiopian Institute of Agricultural Research (EIAR) and CABI PlantwisePlus data, indexed with SQLite FTS5 for BM25 ranked search. Also stores persistent field observations with atomic transactions, WAL mode, and online hot backup/restore.
   - **Open-Meteo REST API:** External meteorological service providing 1–14 day daily weather forecasts without requiring API keys.

2. **Custom Agricultural MCP Server (`agricultural_assistant.server.app`):**
   - Built on the official Model Context Protocol Python SDK (`mcp`).
   - Exposes **8 specialized tools** with typed Pydantic input schemas, field constraints, and error envelopes that allow the LLM to recover:
     - `search_crop_disease`: FTS5 pathology search with EIAR/CABI citations.
     - `get_weather_forecast`: Localized forecast retrieval via Open-Meteo.
     - `record_farm_observation`: Persistent observation storage (write-gated).
     - `get_farm_observation`: ID-based observation retrieval.
     - `list_farm_observations`: Filtered & paginated observation queries.
     - `count_farm_observations`: Aggregated observation counts by crop.
     - `summarize_farm_observations`: Historical distribution summaries by crop/stage.
     - `calculate_agronomic_metrics`: Deterministic Growing Degree Days (GDD) & dry spells.
   - Exposes **MCP Resource:** `crops://catalog` (JSON catalog of staple crops, agroecological zones, and research authorities).
   - Exposes **MCP Prompt:** `agricultural_advisory_prompt` (structured advisory evaluation template).
   - Serves dual transports: **stdio JSON-RPC** for local subprocesses and **Streamable HTTP (`/mcp`)** for network/web MCP clients.

3. **Custom Agricultural MCP Client (`agricultural_assistant.client.mcp_client`):**
   - Implements asynchronous connection lifecycle over stdio transport.
   - Dynamically discovers all registered tools via `list_tools()`.
   - Executes typed tool calls via `call_tool(tool_name, arguments)` and returns structured results.

4. **AI Reasoning Engine (`GeminiAdapter`):**
   - Built with the official Google GenAI SDK (`google-genai`) using `gemini-3.5-flash` / `gemini-3.8-flash`.
   - Converts MCP tool schemas into Gemini OpenAPI function declarations with schema sanitization (`additionalProperties` removal, `anyOf` simplification).
   - Executes multi-turn tool-calling loops with bounded iterations (max 5 rounds) and timeout safeguards.
   - **Write Safety Gate:** Intercepts write tools (`record_farm_observation`), requiring explicit user confirmation before modifying SQLite.
   - **Deterministic Offline Fallback:** If internet is unavailable or free-tier quota spikes (503/429), automatically falls back to deterministic local MCP tool execution so the user always receives verified agronomic data.

5. **Web API Backend (`FastAPI`):**
   - Exposes REST endpoints (`/api/chat`, `/api/health`, `/api/weather/forecast`, `/api/diseases/search`, `/api/observations`, `/api/observations/preview`, `/api/observations/confirm`).
   - Mounts the Streamable HTTP MCP server at `/mcp`.
   - Manages MCP client and database connection lifespans.

6. **Web Frontend (`React + Vite + TypeScript + Tailwind CSS`):**
   - Responsive tabbed navigation: Dashboard, Assistant Chat, Weather, Crop Pathology, and Farm Observations.
   - **Two-Step Write Confirmation:** Modal dialog presents full observation payload for farmer review before executing database writes.

---

## 3. Evidence of Verification

| Deliverable / Requirement | Verification Method | Result & Evidence | Status |
| :--- | :--- | :--- | :--- |
| **Backend Unit & Integration Suite** | `uv run pytest` | **139 tests passed** across models, storage, services, MCP server, client, and Gemini adapter. | `VERIFIED` |
| **Frontend Integration Suite** | `npm test -- --run` | **5 Vitest tests passed** (dashboard, chat, weather, disease search, write confirmation modal). | `VERIFIED` |
| **Frontend Production Build** | `npm run build` | **TypeScript compile & Vite bundle passed** in 6.78s without errors. | `VERIFIED` |
| **MCP Inspector (stdio)** | `npx @modelcontextprotocol/inspector --cli` | Discovered all 8 tools, resources (`crops://catalog`), prompts (`agricultural_advisory_prompt`), and executed tool calls. | `VERIFIED` |
| **MCP Inspector (Streamable HTTP)** | `npx @modelcontextprotocol/inspector --cli --server-url http://127.0.0.1:8001/mcp` | Successfully initialized session, discovered 8 tools, and executed `search_crop_disease` over HTTP. | `VERIFIED` |
| **Live Gemini 2-Tool Calling** | `POST /api/chat` via curl & Python script | Gemini autonomously called `count_farm_observations` and `search_crop_disease` in one turn, synthesizing final answer citing EIAR. | `VERIFIED` |
| **Write-Safety Gating** | API preview/confirm & modal test | Unconfirmed writes never touch SQLite; confirmed writes persist observation #1 successfully. | `VERIFIED` |
| **Zero Secret Leaks** | `git check-ignore .env` & secret audit | `.env` ignored; secrets masked (`***`) in `Settings.__repr__`. | `VERIFIED` |

---

## 4. Reproducing the Two-Tool Live Demo

### Option A: Via Web UI
1. Start backend: `uv run python -m agricultural_assistant.api.app`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173` in your browser.
4. Go to **Chat** tab.
5. Enter: *"I am managing a Teff field in Addis Ababa. Please check how many farm observations we currently have recorded for Teff, and search the agricultural knowledge base for symptoms and management of Teff Leaf Rust."*
6. Gemini invokes `count_farm_observations(crop="Teff")` and `search_crop_disease(crop_name="Teff", symptoms="leaf rust")`, returning the count (1) and EIAR research recommendations.

### Option B: Via Command Line (Reproducible Script)
```bash
uv run python -c "
import asyncio
from agricultural_assistant.client.gemini_adapter import GeminiAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient

async def main():
    c = AgriculturalMCPClient()
    a = GeminiAdapter()
    await c.connect()
    try:
        prompt = 'Check how many observations we have for Teff, and search symptoms of Teff Leaf Rust.'
        res = await a.run_prompt(prompt, c)
        print('Status:', res.get('status'))
        print('Tools Used:', [tc['tool_name'] for tc in res.get('tool_calls_executed', [])])
        print('Response Preview:\n', res.get('llm_response')[:400])
    finally:
        await c.disconnect()

asyncio.run(main())
"
```

---

## 5. Security & Safety Posture
- **API Keys:** Never hardcoded; read from `.env` via `config.py` and masked in all logging outputs.
- **Write Operations:** Mutating tools (`record_farm_observation`) cannot execute without explicit confirmation callback or preview approval.
- **Transport Binding:** Default binding is `127.0.0.1` (loopback) to prevent accidental unauthenticated public exposure.
- **Network Resilience:** Gracefully catches network timeouts and model quota exhaustion, maintaining availability via deterministic offline fallback.
