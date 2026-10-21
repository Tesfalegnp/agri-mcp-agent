# Agricultural MCP Assistant — Architecture & Design Specification

> **System:** Agri MCP Agent  
> **Repository:** [https://github.com/Tesfalegnp/agri-mcp-agent](https://github.com/Tesfalegnp/agri-mcp-agent)  
> **Protocol Specification:** Model Context Protocol (MCP) Python SDK `v2.3.0` (Negotiated Protocol Version: `2026-07-28`)  
> **Security Specification:** Built-in Reference OAuth 2.1 Authorization Service (RFC 8414, RFC 7636 PKCE S256, RFC 7009, RFC 7662)  

---

## 1. End-to-End Architectural Overview

The Agricultural MCP Assistant follows a strict separation of concerns where LLM operations, conversational slot-filling, MCP client discovery, and MCP tool execution are decoupled into distinct layers.

```mermaid
graph TD
    User([Farmer / Agronomist / Evaluator]) <--> WebUI[React + TypeScript + Tailwind Web UI]
    WebUI <-->|HTTP REST & Server-Sent Events SSE| FastAPIServer[FastAPI Application Server :8000]
    
    subgraph Application Backend
        FastAPIServer --> Orchestrator[ConversationOrchestrator]
        Orchestrator --> GeminiAdapter[Gemini / LLM Adapter]
        Orchestrator --> MCPClient[AgriculturalMCPClient]
        FastAPIServer --> OAuthService[OAuth 2.1 Auth Server]
    end

    subgraph LLM Provider Boundary
        GeminiAdapter <-->|Function Calling Protocol| GeminiCloud[Google Gemini 2.5/3.5 Flash API]
    end

    subgraph MCP Transport Boundary
        MCPClient <-->|Transport A: Local Subprocess Stdio| StdioSubprocess[MCP Server Subprocess]
        MCPClient <-->|Transport B: Streamable HTTP with OAuth 2.1 Bearer| HTTPRoute[/mcp Streamable HTTP Endpoint]
        HTTPRoute --> StarletteApp[Starlette MCP Server Engine]
    end

    subgraph MCP Agricultural Capabilities
        StdioSubprocess --> MCPTools[8 Agricultural MCP Tools]
        StarletteApp --> MCPTools
        StdioSubprocess --> MCPResources[Resource: crops://catalog]
        StarletteApp --> MCPResources
        StdioSubprocess --> MCPPrompts[Prompt: agricultural_advisory_prompt]
        StarletteApp --> MCPPrompts
    end

    subgraph External Agricultural Resources
        MCPTools <-->|Resource 1: SQLite FTS5 Pathology Database| DB[(data/agricultural_assistant.db)]
        MCPTools <-->|Resource 2: REST Weather API with Backoff| OpenMeteo[Open-Meteo Global Forecast API]
    end
```

---

## 2. Component Responsibilities

| Layer / Component | Location | Strict Responsibility |
|---|---|---|
| **Web UI** | `frontend/src/` | Provides conversational chat, suggested query cards, real-time activity timeline, transport switcher, OAuth token loader, and MCP Primitives Inspector. Never directly accesses external agricultural APIs. |
| **Application API** | `src/agricultural_assistant/api/routes.py` | Exposes REST endpoints (`/api/chat`, `/api/chat/stream`, `/api/mcp/*`, `/api/oauth/*`), SSE progress piping, and session management. |
| **Agent Orchestrator** | `src/agricultural_assistant/client/orchestrator.py` | State machine governing multi-turn conversations (`idle`, `thinking`, `awaiting_user_input`, `discovering_tools`, `executing_tools`, `processing_results`, `completed`, `cancelled`). Detects missing required parameters before invoking tools, prompts the user, stores pending workflows, and resumes automatically upon clarification. |
| **LLM Adapter** | `src/agricultural_assistant/client/gemini_adapter.py` | Translates MCP tool schemas into provider-native tool declarations (e.g. Google GenAI `Tool` / `FunctionDeclaration`), receives function call requests, and formats execution results back to the model. |
| **MCP Client** | `src/agricultural_assistant/client/mcp_client.py` | Official MCP Python SDK client implementation. Manages session lifecycles for both `stdio` (subprocess) and `streamable-http` (remote HTTP with Bearer tokens). Introspects tools, resources, and prompts. |
| **MCP Server** | `src/agricultural_assistant/server/app.py` | Declares typed tools, input schemas, output schemas, resources, and prompts. Implements domain validation, rate limiting, and safe error handling. Outputs diagnostics strictly to stderr to prevent stdio protocol corruption. |
| **OAuth 2.1 Provider** | `src/agricultural_assistant/server/oauth.py` | Implements RFC 8414 metadata discovery, PKCE (S256) authorization code grant, client credentials, HMAC-SHA256 token verification, scope enforcement (`agri:read`, `agri:write`), and token revocation. |
| **External Resources** | `src/agricultural_assistant/services/` & `storage/` | **Resource 1:** SQLite 3 database with Full-Text Search (FTS5) for crop pathology and farm observations.<br>**Resource 2:** Open-Meteo REST API for live weather forecasts. |

---

## 3. Sequence Diagram — Normal Tool Execution Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Evaluator
    participant UI as Web UI (React)
    participant API as FastAPI Server
    participant Orch as Orchestrator
    participant LLM as Google Gemini AI
    participant Client as MCP Client
    participant Server as MCP Server
    participant Ext as External Resources

    User->>UI: "What is the weather for Jimma and farming risks?"
    UI->>API: POST /api/chat/stream (SSE)
    API->>Orch: process_message(prompt, session_id)
    Orch->>API: Emit: [request_received]
    Orch->>Client: list_tools()
    Client->>Server: JSON-RPC tools/list
    Server-->>Client: 8 Tool Schemas
    Client-->>Orch: Discovered Tools
    Orch->>API: Emit: [tools_discovered (8 tools)]
    Orch->>LLM: Send prompt + System Prompt + Tool Declarations
    LLM-->>Orch: FunctionCall: get_weather_forecast(latitude=7.67, longitude=36.83)
    Orch->>API: Emit: [tool_call_start: get_weather_forecast]
    Orch->>Client: call_tool("get_weather_forecast", args)
    Client->>Server: JSON-RPC tools/call
    Server->>Ext: GET api.open-meteo.com/v1/forecast
    Ext-->>Server: Daily weather JSON
    Server-->>Client: Tool Result JSON
    Client-->>Orch: Formatted Tool Result
    Orch->>API: Emit: [tool_result_received]
    Orch->>LLM: Submit tool results to model
    LLM-->>Orch: Final synthesis & agricultural advisory text
    Orch->>API: Emit: [final_answer_delivered]
    API-->>UI: SSE Data stream with activity timeline + final text
    UI-->>User: Displays advisory, per-tool metrics, and timeline
```

---

## 4. Sequence Diagram — Multi-Turn Clarification & Workflow Resumption

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Evaluator
    participant UI as Web UI
    participant Orch as Orchestrator
    participant Session as Session Store
    participant LLM as Gemini AI / Tool Adapter
    participant Server as MCP Server

    Note over User, Orch: Turn 1: Incomplete Farmer Request
    User->>UI: "Help me prepare an agricultural advisory for my farm."
    UI->>Orch: Turn 1 Input
    Orch->>Orch: Detect intent: 'farm_advisory'
    Orch->>Orch: Required slots: [crop, location] -> Missing: [crop, location]
    Orch->>Session: Store pending_workflow(crop=?, location=?, turn=1)
    Orch-->>UI: State: awaiting_user_input<br>"I can help. Which crop are you growing, and where is your farm located?"

    Note over User, Orch: Turn 2: Providing Missing Information
    User->>UI: "Coffee, in Jimma, Ethiopia."
    UI->>Orch: Turn 2 Input
    Orch->>Session: Load pending_workflow
    Orch->>Orch: Extract slots: crop="coffee", location="Jimma, Ethiopia"
    Orch->>Session: Update slots: [crop=coffee, location=Jimma]
    Orch->>Orch: Check remaining slots: None missing!
    Orch->>Orch: Transition state: executing_tools
    Orch->>Server: call_tool("get_weather_forecast", {latitude: 7.67, longitude: 36.83})
    Server-->>Orch: Weather data
    Orch->>Server: call_tool("search_crop_disease", {crop_name: "coffee", symptoms: "general"})
    Server-->>Orch: Disease knowledge
    Orch->>LLM: Synthesize advisory for Coffee in Jimma with weather & disease data
    LLM-->>Orch: Final Comprehensive Advisory
    Orch-->>UI: State: completed<br>Delivers Coffee Advisory with live execution timeline
```

---

## 5. Transport Comparison: Local stdio vs Streamable HTTP

The Agricultural MCP Assistant natively implements both MCP transport protocols:

| Dimension | Local `stdio` Transport | Remote `Streamable HTTP` Transport |
|---|---|---|
| **Process Model** | Server runs as a local child subprocess managed by `subprocess.Popen` | Server runs within or alongside FastAPI Starlette HTTP engine (`/mcp`) |
| **Communication Channel** | Standard OS input/output streams (`stdin` / `stdout`) | HTTP POST and Server-Sent Events (SSE) streaming sessions |
| **Framing & Encoding** | JSON-RPC 2.0 lines terminated by `\n` | HTTP requests with `Content-Type: application/json` and SSE chunking |
| **Diagnostics & Logs** | Strictly written to `stderr` to avoid JSON-RPC stream corruption | Emitted through standard server logging frameworks |
| **Authentication / Security** | Local OS process boundary (inherits user permissions) | **OAuth 2.1 Protected** via `Authorization: Bearer <token>` |
| **Ideal Deployment** | Desktop IDEs (Claude Desktop, Antigravity IDE, Cursor) | Remote cloud containers, distributed microservices, multi-tenant agent platforms |
| **UI Toggle Mechanism** | Selected via top navigation switch; launches subprocess on demand | Selected via top navigation switch; connects to HTTP endpoint with Bearer token |

---

## 6. OAuth 2.1 Security Architecture

When the application operates over **Streamable HTTP**, endpoints are protected by an OAuth 2.1 authorization server implementation:

```mermaid
graph LR
    ClientApp[Client / Inspector / Web UI] -->|1. /oauth/authorize with PKCE S256| AuthServer[OAuth 2.1 Auth Server]
    AuthServer -->|2. Authorization Code| ClientApp
    ClientApp -->|3. POST /oauth/token code + code_verifier| AuthServer
    AuthServer -->|4. Signed Access Token agri:read agri:write| ClientApp
    ClientApp -->|5. POST /mcp with Bearer Token| MCPAuthMiddleware[OAuthStreamableAuthMiddleware]
    MCPAuthMiddleware -->|6. Valid Token & Scope Match| StarletteMCP[MCP Server Engine /mcp]
    MCPAuthMiddleware -->|7. Invalid / Expired / Unscoped| Reject[401 / 403 Forbidden]
```

### Key Security Controls:
1. **RFC 7636 PKCE:** Mandatory for authorization code grants (`code_challenge_method=S256`).
2. **RFC 8414 Discovery:** Root discovery endpoint available at `/.well-known/oauth-authorization-server`.
3. **Granular Scopes:**
   - `agri:read`: Authorizes read-only operations (weather queries, disease searches, observation listing, metrics).
   - `agri:write`: Authorizes state-modifying operations (`record_farm_observation`). Enforced at the `/mcp` middleware boundary.
4. **Token Verification:** Signed with HMAC-SHA256, verifying issuer, audience (`/mcp`), expiration (`exp`), and active revocation status.
5. **Secret Redaction:** Tokens, client secrets, and database paths are masked in application logs via `sanitize_secrets`.
6. **Implementation Scope & Boundary:** The built-in authorization service is a self-contained reference implementation using symmetric HMAC-SHA256 signing. It does not implement asymmetric JWKS public-key fetching required by third-party enterprise IdPs (e.g. Okta, Auth0); integrating external IdP tokens would require extending the verifier with a JWKS client.
