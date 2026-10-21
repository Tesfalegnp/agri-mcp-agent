# Agricultural MCP Assistant — Evaluator Demonstration Script

> **Goal:** Complete, repeatable 5–8 minute live evaluation demonstration of the Agri MCP Agent.  
> **Repository:** [https://github.com/Tesfalegnp/agri-mcp-agent](https://github.com/Tesfalegnp/agri-mcp-agent)  
> **Prerequisites:** Python 3.12 (`uv`), Node.js (v20+), optional Google Gemini API key (built-in fallback provided if key is unset).

---

## 1. Quick Startup (Under 1 Minute)

### Terminal 1: Launch FastAPI Backend Server
```bash
# From workspace root
uv run uvicorn agricultural_assistant.api.app:app --host 127.0.0.1 --port 8000
```
*Expected Output:*
```text
INFO:     Started server process [pid]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Launch React Frontend
```bash
# In another terminal window
cd frontend
npm run dev
```
*Expected Output:*
```text
  VITE v6.4.4  ready in 250 ms

  ➜  Local:   http://localhost:5173/
```

Open your browser to: **`http://localhost:5173/`**

---

## 2. Demonstration Step-by-Step Walkthrough

### Step 1: Health & Connection State Check (30 seconds)
1. On the top navigation bar, observe the **Live Status Badges**:
   - Status: `Operational` (green dot)
   - Discovered Tools: `8 Tools Ready`
   - Transport Selector: `stdio` is selected by default with a green `Connected` pill.
2. Click **AI Assistant** in the top navigation bar to open the main conversation view.
3. Click the **MCP Inspector** button (top right of the chat panel) to open the Primitives Explorer:
   - View all 8 discovered MCP tools with their typed schemas.
   - Click the **Resources** tab to view `crops://catalog` and click **Read Resource** to see live crop classifications.
   - Click the **Prompts** tab to inspect `agricultural_advisory_prompt`.
   - Close the modal.

---

### Step 2: Live Tool Call with Real-Time Progress Timeline (1.5 minutes)
1. Click the suggested query card:
   > *"Check the current weather for Jimma and explain potential farming risks."*
2. **Observe the Live Activity Timeline:**
   - Notice events appearing sequentially in real-time as Server-Sent Events (SSE) stream in:
     - `User request received`
     - `Conversation context loaded`
     - `Connecting to MCP server (stdio)`
     - `Server tools discovered (8 tools)`
     - `AI model analyzing request and tool requirements`
     - `MCP tool call requested: get_weather_forecast` (summarized coordinates: lat 7.67, lon 36.83)
     - `Tool execution started: Querying Open-Meteo external weather API`
     - `MCP tool result received: Received 3-day weather forecast`
     - `Delivering grounded agricultural answer`
3. Expand the **Activity Timeline** card to view the exact JSON payload returned by Open-Meteo.
4. Read the synthesized assistant response: notice it cites exact temperatures, precipitation numbers, and specific crop risks grounded in the tool output.

---

### Step 3: Multi-Turn Conversation & Missing Information Handling (2 minutes)
1. In the chat input, send an incomplete agricultural query lacking required parameters:
   > *"Help me prepare an agricultural advisory for my farm."*
2. **Observe State Machine Behavior:**
   - Notice the assistant enters `awaiting_user_input` state.
   - The timeline shows: `Additional information required (missing slots: crop, location)`.
   - The assistant asks a natural, focused clarification question:
     > *"I can help. Which crop are you growing, and where is your farm located?"*
3. Provide the missing parameters in a single conversational sentence:
   > *"Coffee, in Jimma, Ethiopia."*
4. **Observe Workflow Resumption:**
   - The assistant **does not** restart from scratch or lose context.
   - The timeline reports: `Slots filled: crop=coffee, location=Jimma, Ethiopia. Resuming pending advisory workflow.`
   - The orchestrator automatically invokes:
     - `get_weather_forecast` for Jimma coordinates.
     - `search_crop_disease` for coffee pathology in SQLite.
   - The assistant delivers a tailored, comprehensive advisory for coffee growers in Jimma, taking into account current weather and prevalent coffee diseases (e.g. Coffee Leaf Rust).

---

### Step 4: Transport Switching (stdio ⇄ Streamable HTTP) (1 minute)
1. Look at the **MCP Transport Selector** in the chat header.
2. Click **Streamable HTTP**.
3. The UI issues `POST /api/mcp/transport` to reconfigure the client.
4. If OAuth token is not yet provided, observe the status: `HTTP 401 Unauthorized` (confirming remote endpoint protection).
5. Click the **OAuth 2.1 Demo: Load Demo Token** button.
   - The frontend calls `/api/oauth/demo-token` to obtain an authorized JWT token (`agri:read agri:write`).
   - The status updates to `Connected (Streamable HTTP)` with green active indicator.
6. Submit a query over HTTP:
   > *"Show me which MCP tools are available."*
7. Observe that the exact same 8 tools are discovered and invoked over remote Streamable HTTP.
8. Switch back to **stdio** at any time with a single click.

---

### Step 5: Write-Safety Confirmation Flow (1 minute)
1. Click **Farm Records** in the navigation bar.
2. Click **Record New Observation**.
3. Enter:
   - Crop: `Coffee`
   - Location: `Jimma Plot 2`
   - Symptoms / Notes: `Observed yellow rust spots on underside of leaves`
4. Click **Review & Authorize Record**:
   - Notice the **Write Authorization Required** safety modal.
   - Explains that write operations modify persistent state in SQLite and require explicit farmer authorization.
5. Click **Authorize & Save Record**:
   - The record is written to SQLite.
   - Return to the **Observations List** tab to verify the newly inserted observation.

---

### Step 6: Official MCP Inspector CLI Demonstration (1 minute)
In your terminal, execute the official MCP inspector command to demonstrate protocol conformance:
```bash
npx @modelcontextprotocol/inspector --cli --method tools/list uv run agricultural-assistant-server
```
Observe that the official inspector connects via stdio and outputs the complete JSON catalog of all 8 tools with zero errors.

---

## 3. Demonstration Evaluation Checklist

| Checklist Item | Evaluator Verification Point | Status |
|---|---|:---:|
| **1. Genuine MCP Architecture** | Web UI → FastAPI → Orchestrator → LLM ⇄ MCP Client ⇄ MCP Server ⇄ External Resources | **VERIFIED** |
| **2. Multi-Turn Clarification** | Asks for missing crop/location, preserves session ID, resumes workflow seamlessly | **VERIFIED** |
| **3. External Resources** | SQLite 3 FTS5 pathology database + Open-Meteo live weather API | **VERIFIED** |
| **4. Dual Transports** | Both `stdio` (subprocess) and `streamable-http` (HTTP/SSE) function and toggle in UI | **VERIFIED** |
| **5. OAuth 2.1 Security** | PKCE S256, RFC 8414 metadata, Bearer tokens, scopes (`agri:read`, `agri:write`) protect `/mcp` | **VERIFIED** |
| **6. Live Progress UI** | Genuine Server-Sent Events (SSE) timeline displaying per-step execution status and durations | **VERIFIED** |
| **7. Official MCP Inspector** | Conformance verified using `@modelcontextprotocol/inspector --cli` | **VERIFIED** |
