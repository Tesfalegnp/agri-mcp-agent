# Agricultural MCP Assistant

<p align="center">
  <img src="docs/assets/mcp-main.gif" alt="Model Context Protocol (MCP) Architecture Overview" width="750" />
</p>

A production-grade, full-stack, AI-powered agricultural decision-support system designed for smallholder farmers, agricultural extension workers, and agronomists. It integrates crop disease pathology search, localized meteorological forecasts, persistent farm observation management, historical trend summaries, and deterministic agronomic calculations using Google Gemini tool calling and the Model Context Protocol (MCP) over both **stdio and Streamable HTTP transports**.

---

## A. Project Overview

The **Agricultural MCP Assistant** bridges modern foundation AI models with local agricultural realities. Smallholder farming communities face significant barriers in accessing timely, localized, and evidence-grounded agronomic expertise. Symptoms of devastating crop diseases (such as Coffee Leaf Rust, Maize Fall Armyworm, or Wheat Stem Rust) are often identified too late, and localized weather volatility complicates planting and spraying schedules.

### Problems Addressed
1. **Access to Vetted Agricultural Knowledge:** Provides instant access to pathology data sourced directly from the **Ethiopian Institute of Agricultural Research (EIAR)** and **CABI PlantwisePlus Knowledge Bank**, avoiding unverified hallucinated treatments.
2. **Actionable Weather Intelligence:** Delivers localized 1–14 day high-resolution meteorological forecasts via **Open-Meteo** without requiring paid API access.
3. **Structured Field Recordkeeping:** Replaces lost paper records with a local SQLite database that records field observations, phenological stages, and spatial coordinates.
4. **Data-Driven Agronomic Insights:** Deterministically computes critical thermal heat units (Growing Degree Days - GDD) and precipitation dry-spell indices from daily weather records.
5. **Safe AI Interaction:** Enforces strict **human-in-the-loop write safety**; the AI assistant can suggest and draft farm observations, but never mutates the database without explicit user confirmation.

### Role of the Model Context Protocol (MCP)
The Model Context Protocol (MCP) provides an open, standardized contract decoupling the AI reasoning engine from tool execution and data persistence. In this project:
- **Shared Agricultural Tools:** 8 specialized agricultural tools are registered once in a shared service layer.
- **Dual Transports:** The MCP server natively serves both **local stdio** (for local CLI and desktop host applications like Claude Desktop or Cursor) and **Streamable HTTP** (`/mcp` endpoint for remote and web-based MCP clients).
- **Extensible:** Allows any MCP-compliant client to consume agricultural intelligence, resources, and prompt templates without modifying backend business logic.

---

## B. Feature List

- **Gemini-Powered Agricultural Assistant:** Multi-turn conversational guidance powered by Google Gemini (`gemini-3.5-flash` / `gemini-3.8-flash`) via the official Google GenAI SDK (`google-genai`).
- **Autonomous MCP Tool Calling:** The AI assistant dynamically discovers available MCP tools, executes requested functions through the MCP client, and synthesizes evidence-grounded answers with research citations.
- **Dual MCP Transports:**
  - **Local stdio Transport:** Standard input/output JSON-RPC for local clients and background CLI operations.
  - **Streamable HTTP Transport:** Standards-compliant MCP Streamable HTTP endpoint (`/mcp`) supporting initialization, session lifecycle, SSE streaming, and HTTP POST/DELETE methods.
- **MCP Prompts & Resources:**
  - Resource: `crops://catalog` (curated catalog of supported crops, scientific classifications, and agroecological zones).
  - Prompt: `agricultural_advisory_prompt` (structured prompt template for agronomic symptom evaluation).
- **Vetted Crop Disease Search:** Full-text search (SQLite FTS5) across regional pathology databases with symptoms, cultural practices, IPM recommendations, and source attribution.
- **Localized Weather Forecasts:** 1–14 day forecasts (temperatures, rainfall sum, precipitation probability) with regional Ethiopian presets (Addis Ababa, Jimma, Hawassa, Bahir Dar, Mekelle).
- **Farm Observations Management:**
  - Form validation with phenological growth stages.
  - Mandatory **two-step review and explicit confirmation** modal before database write.
  - Paginated observation history with crop-based filtering.
  - Statistical summary distributions by crop and growth stage.
- **Deterministic Agronomic Calculator:** Mathematical Growing Degree Days (GDD) with customizable base and cutoff temperatures, plus precipitation dry-day threshold analysis.
- **Deterministic Offline Fallback:** If internet connectivity is interrupted or Gemini free-tier quota is exhausted, the backend falls back to an offline deterministic intent resolver, allowing full local UI testing and development.
- **Point-in-Time SQLite Backup & Restore:** Online non-blocking database backup and restore via SQLite's native backup API.

---

## C. Architecture and Request Flows

### System Architecture Diagram

```mermaid
graph TD
    Farmer([Farmer / Agronomist]) <-->|Browser| ReactUI[React 18 + Vite + Tailwind CSS Web UI]
    ExternalMCP[External MCP Client: Claude Desktop / Cursor / SDK] <-->|Streamable HTTP /mcp| FastAPIServer
    LocalCLI[Local Terminal CLI] <-->|stdio JSON-RPC| MCPServerStdio[Agricultural MCP Server stdio]

    subgraph Python Backend Application
        ReactUI <-->|HTTP REST JSON| FastAPIServer[FastAPI Backend Server :8000]
        FastAPIServer <-->|Streamable HTTP Mount /mcp| MCPServerHTTP[MCP Streamable HTTP Server]

        FastAPIServer <--> GeminiAdapter[GeminiAdapter / google-genai SDK]
        FastAPIServer <--> ObservService[ObservationService]
        FastAPIServer <--> CropService[CropService]
        FastAPIServer <--> WeatherService[WeatherService]
        FastAPIServer <--> InsightsService[FarmInsightsService / AgronomicCalculator]

        GeminiAdapter <-->|Tool Execution Request| LocalMCPClient[Agricultural MCP Client]
        LocalMCPClient <-->|stdio JSON-RPC| MCPServerStdio

        subgraph Shared Agricultural Tool Layer
            MCPServerStdio --> Tools[8 Registered MCP Tools + Prompts + Resources]
            MCPServerHTTP --> Tools
        end

        Tools --> FTS5Repo[KnowledgeRepository - FTS5 Search]
        Tools --> ObsRepo[ObservationRepository]
        Tools --> WeatherAPI[WeatherService - Open-Meteo REST]
        Tools --> MathEngine[AgronomicCalculator - Deterministic Math]

        FTS5Repo --> SQLiteDB[(SQLite Database + FTS5 Index)]
        ObsRepo --> SQLiteDB
    end

    WeatherAPI <-->|HTTPS| OpenMeteoCloud[Open-Meteo Weather API]
```

### End-to-End Request Flows

#### 1. Asking an Agricultural Question (Web Chat)
1. Farmer enters: *"What are common symptoms of coffee leaf rust in Jimma?"* in the React chat interface.
2. React frontend issues `POST /api/chat` to the FastAPI backend.
3. `GeminiAdapter` receives the prompt, queries the MCP client for registered tool definitions, and converts them to Gemini `types.FunctionDeclaration`.
4. Gemini returns a tool-call request for `search_crop_disease(crop_name="Coffee", symptoms="rust")`.
5. `GeminiAdapter` passes the tool call to `AgriculturalMCPClient`, which invokes the tool over stdio on the local MCP server.
6. The MCP server executes SQLite FTS5 search and returns matching pathology data citing EIAR and CABI.
7. `GeminiAdapter` delivers tool results back to Gemini.
8. Gemini synthesizes a plain-language answer explaining symptoms, cultural management, and research citations, which appears in the chat UI.

#### 2. Recording a Farm Observation with Explicit Confirmation
1. Farmer fills in the Observation form (Crop: Coffee, Stage: Vegetative, Notes: *"Found orange powdery lesions on undersides of leaves"*, Location: Jimma).
2. Clicking **"Preview Observation"** submits `POST /api/observations/preview`. The backend validates all fields against domain constraints and returns a formatted preview.
3. The React UI displays the **Write Confirmation Modal**.
4. The database is **not** touched until the farmer explicitly clicks **"Authorize & Save Record"**.
5. The frontend sends `POST /api/observations/confirm`.
6. The backend invokes `record_farm_observation` via the MCP client, committing the row to SQLite and returning the new record ID.

#### 3. Connecting an MCP Client via Streamable HTTP
1. An external client (e.g. Python MCP SDK or remote IDE) connects to `http://localhost:8000/mcp`.
2. The client sends an HTTP POST with JSON-RPC initialization request (`initialize`).
3. The server assigns an MCP session ID, negotiates protocol version, and advertises capabilities.
4. The client issues `tools/list` to discover all 8 tools, `prompts/list` for advisory prompts, and `resources/list` for crop catalogs.
5. The client invokes `tools/call` with tool arguments and receives structured JSON results.
6. Upon closing, the client sends an HTTP DELETE request to cleanly terminate the session.

---

## D. Technology Stack

- **AI Engine:** Google Gemini 2.5 Flash via official `google-genai` SDK (v2.31.0+).
- **Model Context Protocol:** Official MCP Python SDK (`mcp` v2.3.0) with stdio and Streamable HTTP transports.
- **Backend Framework:** FastAPI (v0.115.0+), Uvicorn, Starlette, AnyIO, Pydantic (v2.10.0+).
- **Frontend Stack:** React 18, Vite 6, TypeScript 5.7, Tailwind CSS 3.4, Lucide React icons.
- **Database & Search:** SQLite 3 with WAL journal mode, parameterized SQL transactions, and SQLite FTS5 (Full-Text Search).
- **External Meteorological API:** Open-Meteo Weather Forecast API.
- **Testing Frameworks:** Pytest 9, Pytest-AnyIO, Vitest 5, React Testing Library, JSDOM.
- **Package & Dependency Management:** `uv` (Python), `npm` (Node.js).

---

## E. Prerequisites

- **Python:** Version 3.11 or 3.12+ installed.
- **uv:** Fast Python package and project manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- **Node.js & npm:** Node.js v18+ and `npm` installed.
- **Internet Connectivity:** Required for live Open-Meteo weather forecasts and live Google Gemini API calls.
- **Gemini API Key (Optional for Local Dev/Testing):** A Google AI Studio API key (`GEMINI_API_KEY`) for live AI responses. All automated unit, integration, and UI tests work 100% offline without an API key.

---

## F. Clone and Install

### 1. Clone the Repository
```bash
git clone https://github.com/Tesfalegnp/agri-mcp-agent.git
cd agri-mcp-agent
```
*(If checking out locally, use `cd /home/hope/Projects/agricultural-mcp-assistant`)*

### 2. Install Backend Python Dependencies
```bash
# Sync backend virtual environment with all core and test dependencies
uv sync --extra dev
```

### 3. Install Frontend Node Dependencies
```bash
cd frontend
npm install
cd ..
```

### 4. Database Setup
The SQLite database and FTS5 search index are initialized automatically with sample crop disease data upon backend startup. You can also trigger database initialization manually:
```bash
uv run python -c "from agricultural_assistant.storage.database import DatabaseManager; DatabaseManager().initialize()"
```

---

## G. Environment Configuration

### Setup `.env`
Copy `.env.example` to create your local `.env`:
```bash
cp .env.example .env
```

### Supported Configuration Variables

| Variable | Required | Default Value | Purpose |
| :--- | :---: | :--- | :--- |
| `GEMINI_API_KEY` | Optional | `None` | Google Gemini API key from Google AI Studio. |
| `GEMINI_MODEL` | Optional | `gemini-3.5-flash` | Gemini model name on the free tier (`gemini-3.5-flash` or `gemini-3.8-flash`). |
| `BACKEND_HOST` | Optional | `127.0.0.1` | Host address for the FastAPI backend server. |
| `BACKEND_PORT` | Optional | `8000` | Port for the FastAPI backend server. |
| `CORS_ORIGINS` | Optional | `http://localhost:5173,http://127.0.0.1:5173` | Allowed frontend origins for CORS. |
| `DATABASE_PATH` | Optional | `data/agricultural_assistant.db` | Relative or absolute path to SQLite database. |
| `OPEN_METEO_BASE_URL` | Optional | `https://api.open-meteo.com/v1/forecast` | Open-Meteo REST API endpoint. |
| `LOG_LEVEL` | Optional | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `VITE_API_BASE_URL` | Optional | `http://localhost:8000` | Frontend backend API target URL. |

> **Security Notice:** `.env` is ignored by Git. Real API keys must never be committed.

---

## H. Run the Complete Application

### Terminal 1: Start the Backend Web API & Streamable HTTP Server
```bash
# Run backend on http://127.0.0.1:8000 (serves REST API + /mcp Streamable HTTP endpoint)
uv run uvicorn src.agricultural_assistant.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2: Start the React Frontend Development Server
```bash
cd frontend
npm run dev
```

### Access Application
Open **`http://localhost:5173`** in your browser.

### Health Check
Verify backend and MCP client status:
```bash
curl -s http://127.0.0.1:8000/api/health | jq
```
Expected output:
```json
{
  "status": "healthy",
  "mcp_server_connected": true,
  "tools_discovered": 8,
  "service": "Agricultural MCP Assistant",
  "version": "0.1.0"
}
```

---

## I. Run Both MCP Transports

### 1. Local stdio Transport

#### Start stdio Server Directly
```bash
uv run python -m agricultural_assistant.server.app --transport stdio
```

#### Client Configuration Example (Claude Desktop / Cursor)
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "agricultural-assistant": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/hope/Projects/agricultural-mcp-assistant",
        "run",
        "python",
        "-m",
        "agricultural_assistant.server.app",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

### 2. Streamable HTTP Transport

#### Built-in with Web Backend
The Streamable HTTP transport is automatically mounted on the web backend at:
**`http://127.0.0.1:8000/mcp`**

#### Or Run as Standalone Server
```bash
uv run python -m agricultural_assistant.server.app --transport streamable-http --port 8001 --path /mcp
```

#### Test Streamable HTTP with Python Client
```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("http://127.0.0.1:8000/mcp") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Discovered {len(tools.tools)} tools over Streamable HTTP!")

            result = await session.call_tool(
                "search_crop_disease",
                arguments={"crop_name": "Teff", "symptoms": "rust spots"}
            )
            print("Tool result:", result.content[0].text[:120])

asyncio.run(main())
```

---

## J. Demonstration Walkthrough

Follow these steps to demonstrate the full application:

1. **Start Services:** Start backend on `:8000` and frontend on `:5173` as shown in Section H.
2. **Open Dashboard:** Navigate to `http://localhost:5173`. Confirm the health indicator displays `"System Healthy — 8 MCP Tools Connected"`.
3. **Ask an Agricultural Question (Chat):**
   - Click the **AI Assistant** tab.
   - Click the prompt chip: *"What are common symptoms of coffee leaf rust?"*
   - Observe the tool execution badge (`search_crop_disease`) and review the synthesized response citing EIAR and CABI with IPM cultural recommendations.
4. **Inspect Weather Forecast:**
   - Click the **Weather** tab.
   - Click the **Jimma** preset button.
   - Verify that 3-day temperatures, precipitation probability, and rainfall amounts are displayed directly from Open-Meteo.
5. **Search Crop Pathology Knowledge:**
   - Click the **Crop Pathology** tab.
   - Select **Maize** and enter symptoms: `holes in leaves and whorl damage`.
   - View the matching record for **Fall Armyworm (*Spodoptera frugiperda*)** with cultural and biological control recommendations.
6. **Record a Farm Observation with Confirmation:**
   - Click the **Farm Records** tab.
   - Select Crop: `Wheat`, Growth Stage: `Heading`, Location: `Bale Zone`.
   - Notes: `Yellow rust pustules observed in strips on leaf blades`.
   - Click **"Preview Observation"**.
   - Review the details in the **Write Authorization Modal**.
   - Click **"Authorize & Save Record"**.
   - Confirm the success alert and verify the new record appears immediately in the **Recorded Observations** list.
7. **Compute Agronomic Metrics:**
   - Scroll to **Agronomic Metrics Calculator** on the Farm Records page.
   - Enter Base Temperature: `10.0°C`, click **"Calculate GDD & Rain Indices"**.
   - Verify the calculated Cumulative GDD and Dry Spell summary.
8. **Verify Streamable HTTP MCP Access:**
   - In a terminal, run the protocol test: `uv run pytest tests/test_streamable_http.py`.
   - Verify that all 4 tests pass, confirming external client connectivity, capability negotiation, and tool execution over Streamable HTTP.

---

## K. Tests and Verification

### 1. Full Python Test Suite (139 Passing Tests)
```bash
uv run pytest -v
```
**Outcome:** **139 passed in ~16 seconds**
- `test_config.py`: 3 tests (secret masking, env loading)
- `test_crop_models.py`: 6 tests (validation, enums)
- `test_weather_models.py`: 10 tests (coordinate bounds, forecast days)
- `test_observation_models.py`: 11 tests (note length, coordinates)
- `test_database.py`: 4 tests (WAL mode, transactions, point-in-time backup/restore)
- `test_knowledge_repository.py`: 6 tests (FTS5 search, seeding, BM25 ranking)
- `test_observation_repository.py`: 5 tests (CRUD, SQL injection safety)
- `test_weather_service.py`: 6 tests (Open-Meteo mock, timeouts, errors)
- `test_crop_service.py`: 5 tests (caching, query parsing)
- `test_observation_service.py`: 6 tests (service validation, pagination)
- `test_insights_service.py`: 6 tests (mathematical GDD and rainfall index calculations)
- `test_server.py`: 7 tests (stdio MCP server tools, schema validation)
- `test_observation_tools.py`: 3 tests (observation tool discovery and execution)
- `test_insights_tools.py`: 3 tests (insights tool execution)
- `test_client.py`: 3 tests (custom MCP client session lifecycle)
- `test_end_to_end_mcp.py`: 1 test (end-to-end stdio tool discovery and invocation)
- `test_streamable_http.py`: 4 tests (Streamable HTTP initialization, tools, prompts, resources, tool calls)
- `test_gemini_adapter.py`: 11 tests (Gemini tool mapping, tool loop, write safety, offline fallback)
- `test_api_routes.py`: 11 tests (FastAPI endpoints, validation, preview/confirm flow)
- `test_llm_adapter.py`: 13 tests (legacy LLM regression tests)

### 2. Frontend Test Suite (5 Passing Tests)
```bash
cd frontend
npm test -- --run
```
**Outcome:** **5 passed in 2.15 seconds**
- Dashboard title & health indicator
- Chat submission and assistant response
- Weather forecast display with regional presets
- Crop pathology search with EIAR/CABI attribution
- Explicit confirmation modal for observation writes

### 3. Production Bundle Build
```bash
cd frontend
npm run build
```
**Outcome:** Built successfully in ~8.5 seconds (`dist/index.html` + asset bundles).

### 4. Python Compilation Check
```bash
uv run python -m py_compile src/agricultural_assistant/**/*.py tests/*.py
```
**Outcome:** Clean compilation with 0 syntax or type errors.

---

## L. Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Gemini Quota Exhausted (`429`)** | Gemini free-tier rate limit exceeded. | The backend automatically activates its deterministic offline intent resolver. You can continue using all tools and UI features without interruption. |
| **Backend Port Conflict (`8000`)** | Another process is using port 8000. | Start on a different port: `uv run uvicorn src.agricultural_assistant.api.app:create_app --factory --port 8005`, and update `VITE_API_BASE_URL` in `frontend/.env`. |
| **`Connection Refused` in Frontend** | Backend server is not running. | Run `uv run uvicorn src.agricultural_assistant.api.app:create_app --factory --port 8000` in Terminal 1. |
| **CORS Error in Browser** | Frontend origin not in allowed list. | Ensure `CORS_ORIGINS` in `.env` includes your frontend URL (default: `http://localhost:5173`). |
| **MCP stdio Protocol Pollution** | Debug statements printed to `stdout`. | Ensure all server logging uses `logger.info()` (which writes to `stderr`) and never raw `print()` statements. |
| **Streamable HTTP `404 Not Found`** | Connecting to wrong path. | Connect to `/mcp` (e.g. `http://localhost:8000/mcp`), not ordinary REST endpoints. |
| **Database Missing / Not Initialized** | First-time clone without database file. | Automatically initialized at startup; or run `DatabaseManager().initialize()`. |

---

## M. Limitations and Future Improvements

### Current Verified Capabilities
- 8 agricultural tools tested and operational across stdio and Streamable HTTP.
- Offline-safe deterministic fallbacks for Gemini AI interactions.
- Sourced disease pathology for 5 key crops (Teff, Maize, Coffee, Wheat, Sorghum).
- Point-in-time online SQLite backup and restore.

### Limitations & Next Steps (Phase 8+)
- **Production Containerization:** Docker and Docker Compose configuration for multi-container deployment.
- **User Authentication:** Single-user local deployment; multi-tenant OAuth2/OIDC is recommended before public web exposure.
- **Image-Based Diagnosis:** Current crop disease tool is symptom-text based; computer vision model integration for leaf photos is planned for future phases.
- **Multilingual UI:** Backend domain models support language codes (`en`, `am`, `om`, `ti`); full localized Amharic and Afaan Oromo UI translations can be added.

---

## N. Contribution and Project Structure

```text
agricultural-mcp-assistant/
├── .env.example                      # Sanitized environment template
├── .gitignore                        # Git exclusion rules (ignores .env, db, dist, node_modules)
├── pyproject.toml                    # Python project configuration & dependencies
├── README.md                         # Project documentation
├── docs/
│   └── phase-completion-matrix.md   # Requirement completion tracking across all phases
├── src/
│   └── agricultural_assistant/
│       ├── api/
│       │   ├── app.py                # FastAPI factory, lifespan, CORS, Streamable HTTP mount
│       │   └── routes.py             # REST endpoints (/api/chat, /weather, /diseases, etc.)
│       ├── client/
│       │   ├── cli.py                # Interactive terminal client
│       │   ├── gemini_adapter.py     # Gemini SDK tool calling & write safety intercept
│       │   └── mcp_client.py         # Custom asynchronous stdio MCP client
│       ├── config.py                 # Pydantic Settings with secret masking
│       ├── domain/                   # Pydantic models (crop, weather, observation)
│       ├── logging_config.py         # stderr logging configuration
│       ├── server/
│       │   └── app.py                # MCP Server with 8 tools, prompts, resources & multi-transport CLI
│       ├── services/                 # Business services (weather, crop, observations, insights)
│       └── storage/                  # SQLite DatabaseManager, FTS5 repository, migrations
├── frontend/
│   ├── src/
│   │   ├── api/client.ts             # Typed API client
│   │   ├── components/               # Navbar, WriteConfirmModal
│   │   ├── pages/                    # Dashboard, Chat, Weather, Diseases, Observations
│   │   ├── App.tsx                   # Main React routing and layout
│   │   └── test/App.test.tsx         # Vitest integration tests
│   ├── package.json
│   └── vite.config.ts
└── tests/                            # Comprehensive test suite (138 pytest tests)
    ├── test_api_routes.py
    ├── test_database.py              # Includes online backup/restore test
    ├── test_gemini_adapter.py
    ├── test_streamable_http.py       # Protocol-level Streamable HTTP tests
    └── ...
```

### Adding a New Agricultural Tool
To add a new tool without duplicating logic:
1. Implement the domain service logic in `src/agricultural_assistant/services/`.
2. Register the tool in `create_server()` in `src/agricultural_assistant/server/app.py` using `@app.tool()`.
3. Because both stdio and Streamable HTTP share `create_server()`, the tool is immediately available over both transports and to the Gemini AI assistant automatically!

---

## O. License and Acknowledgments

### Data & Research Sources
- **Ethiopian Institute of Agricultural Research (EIAR):** Crop pathology guidelines, regional agroecological classifications, and cultivar base temperatures.
- **CABI PlantwisePlus Knowledge Bank:** Open-access Integrated Pest Management (IPM) guidelines.
- **Open-Meteo:** High-resolution meteorological data under Open Database License (ODbL).

### Open Source Libraries
- Model Context Protocol Python SDK (`mcp`) by Anthropic.
- Google GenAI SDK (`google-genai`) by Google DeepMind.
- FastAPI by Sebastián Ramírez.
- Lucide Icons by Lucide Contributors.
