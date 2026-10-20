# Agricultural MCP Assistant

An AI-powered agricultural assistant designed to assist smallholder farmers, agricultural extension workers, and agronomists with crop disease assessment, localized weather advisories, persistent farm observation recording, historical trend summaries, and deterministic agronomic calculations using the Model Context Protocol (MCP).

> **Current Project Status (Phase 5 Complete):**
> * **Phase 2–4:** Pydantic domain models, stdio-based MCP server (`MCPServer`), async MCP client, interactive menu CLI, and decoupled LLM agent adapter.
> * **Phase 5A (Persistence):** Robust SQLite relational storage with connection safety, transactions, schema migrations, and 4 farm observation MCP tools (`record_farm_observation`, `get_farm_observation`, `list_farm_observations`, `count_farm_observations`).
> * **Phase 5B (Insights):** Historical observation statistical summarizer and deterministic agronomic calculations for Growing Degree Days (GDD) and precipitation patterns (`summarize_farm_observations`, `calculate_agronomic_metrics`).
> * **Phase 5C (Searchable Knowledge):** SQLite Full-Text Search (FTS5) backed crop pathology and pest repository with rank-scoring, seed deduplication, source attribution, and multilingual-ready schema.
> * **Phase 5D (Integration):** 10-option interactive CLI menu, dynamic LLM tool discovery and execution, comprehensive test coverage (102 passing tests), and production documentation.

---

## 1. Use Case & Architecture

### The Problem
Smallholder farmers and agricultural extension workers often face challenges identifying crop diseases, anticipating micro-climate weather risks, keeping systematic field observation records across growing seasons, and calculating thermal growth units. Standard general-purpose LLMs lack access to real-time local weather forecasts, verified regional agronomic databases, and reliable persistent storage.

### The Solution with MCP
The Model Context Protocol (MCP) standardizes how LLM applications interact with local tools, live data, and private context. The assistant connects an interactive client or agent to:
1. **Full-Text Crop Knowledge Base:** SQLite FTS5-indexed symptom-to-remedy mappings for Ethiopian staple crops (Teff, Maize, Wheat, Coffee, Sorghum) with strict source attribution and research citations (EIAR, FAO, CABI).
2. **Weather Service:** High-resolution meteorological forecasts via latitude/longitude coordinates (Open-Meteo REST API).
3. **Persistent Farm Observation Storage:** Local SQLite database recording field notes, crop stages, timestamps, location names, and GPS coordinates with foreign keys, WAL mode, and atomic transactions.
4. **Historical Insights & Agronomic Calculations:** Statistical observation aggregations and transparent, deterministic agronomic calculations (Growing Degree Days and precipitation analysis).

### Application Architecture
```text
User / Extension Worker
        │
        ▼
 Agricultural Assistant CLI (client/cli.py)
        │
        ▼
   MCP Client Session (client/mcp_client.py)
        │
        ▼ [stdio JSON-RPC Transport]
   Agricultural MCP Server (server/app.py)
        │
        ├──────────────────────┬──────────────────────┬──────────────────────┐
        │                      │                      │                      │
        ▼                      ▼                      ▼                      ▼
  Crop Knowledge        Weather Service        Observation Service    Agronomic Calculator
 (storage/knowledge)   (services/weather)     (storage/observation)  (services/insights)
        │                      │                      │                      │
        ▼                      ▼                      ▼                      ▼
   SQLite FTS5           Open-Meteo API           SQLite DB            Deterministic Math
 (crop_knowledge_fts)   (REST over HTTPX)     (farm_observations)    (GDD & Rainfall Index)
        │                      │                      │                      │
        ▼                      ▼                      ▼                      ▼
   Crop Search          Weather Forecast       History & Summaries     Thermal Heat Units
```

---

## 2. Selected Technologies & Environment

* **Language:** Python 3.12 (specifically `3.12.15`, managed via `uv`)
* **Package Manager & Resolver:** `uv` (`0.13.1`)
* **MCP SDK:** `mcp==2.3.0` (Official Python SDK 2.x using `MCPServer`, `stdio_server`, `stdio_client`, and `ClientSession` APIs)
* **Database & Search:** SQLite 3 (`sqlite3` standard library) with Write-Ahead Logging (`WAL`), foreign key enforcement, and Full-Text Search 5 (`FTS5`)
* **Data Validation:** `pydantic==2.14.1`
* **HTTP Client:** `httpx==0.28.1`
* **Test Runner:** `pytest==9.1.1` (102 automated tests)

---

## 3. Storage Architecture & Configuration

### SQLite Storage Design
The persistence layer resides in `src/agricultural_assistant/storage/` and is divided into clean responsibilities:
* `database.py`: Manages SQLite connections, pragmas (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;`), and transaction context managers (`with db.transaction() as conn:`).
* `migrations.py`: Schema version tracking table (`schema_migrations`) and numbered migration steps. Automatically applies unapplied migrations on startup.
* `observation_repository.py`: Parameterized SQL queries for inserting, fetching by ID, listing with pagination (`LIMIT`/`OFFSET`) and date/crop filtering, and counting farm observations.
* `knowledge_repository.py`: SQLite FTS5 virtual table indexing for crop diseases and pests, ranking via `bm25` (with fallback to `LIKE` ranking if needed), seed deduplication, and multilingual schema fields.

### Database Path Configuration
The database path is managed through `Settings` in `src/agricultural_assistant/config.py`:
* Default path: `data/agricultural_assistant.db` (created automatically within the workspace data directory).
* Environment variable override: `DATABASE_PATH=/path/to/custom/db.sqlite`.
* In-memory mode for tests: `DATABASE_PATH=:memory:`.
* Git safety: Runtime database files (`*.db`, `*.db-wal`, `*.db-shm`) and the `data/` directory are excluded from Git via `.gitignore`.

### Schema Migrations
Database schema is managed deterministically via `MigrationRunner`:
* **Migration 1 (`create_observations_table`):**
  ```sql
  CREATE TABLE IF NOT EXISTS farm_observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      crop TEXT NOT NULL,
      notes TEXT NOT NULL,
      growth_stage TEXT,
      observed_at TEXT NOT NULL,
      location_name TEXT,
      latitude REAL,
      longitude REAL,
      observer_role TEXT,
      created_at TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_obs_crop ON farm_observations(crop);
  CREATE INDEX IF NOT EXISTS idx_obs_observed_at ON farm_observations(observed_at);
  ```
* **Migration 2 (`create_knowledge_and_fts_tables`):**
  ```sql
  CREATE TABLE IF NOT EXISTS crop_knowledge (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      crop_name TEXT NOT NULL,
      disease_or_pest TEXT NOT NULL,
      symptoms TEXT NOT NULL,
      contributing_conditions TEXT,
      management_practices TEXT NOT NULL,
      source_reference TEXT NOT NULL,
      verification_status TEXT NOT NULL DEFAULT 'verified',
      language TEXT NOT NULL DEFAULT 'en',
      created_at TEXT NOT NULL,
      CONSTRAINT uq_crop_disease_lang UNIQUE (crop_name, disease_or_pest, language)
  );
  CREATE VIRTUAL TABLE IF NOT EXISTS crop_knowledge_fts USING fts5(
      crop_name,
      disease_or_pest,
      symptoms,
      contributing_conditions,
      management_practices,
      content='crop_knowledge',
      content_rowid='id'
  );
  ```

---

## 4. MCP Tools Implemented (8 Tools)

All tools are registered on the stdio MCP server (`server/app.py`):

| Tool Name | Purpose | Primary Parameters |
| :--- | :--- | :--- |
| `search_crop_disease` | Search agronomic knowledge base for disease matches via SQLite FTS5 | `crop_name`, `symptoms`, `growth_stage` (opt), `language` (opt) |
| `get_weather_forecast` | Fetch live 1–14 day forecast from Open-Meteo | `latitude`, `longitude`, `forecast_days` (opt), `crop_context` (opt) |
| `record_farm_observation`| Validate and persist a new field observation into SQLite | `crop`, `notes`, `growth_stage` (opt), `location_name` (opt), `latitude` (opt), `longitude` (opt), `observer_role` (opt) |
| `get_farm_observation` | Fetch a single saved observation by its primary key ID | `observation_id` (integer) |
| `list_farm_observations`| Retrieve paginated observation records with crop and date filters | `crop` (opt), `limit` (opt, max 100), `offset` (opt), `start_date` (opt), `end_date` (opt) |
| `count_farm_observations`| Count total recorded observations matching filter criteria | `crop` (opt) |
| `summarize_farm_observations` | Aggregate observations by crop, stage, date range, and symptom mentions | `crop` (opt), `start_date` (opt), `end_date` (opt) |
| `calculate_agronomic_metrics` | Calculate Growing Degree Days (GDD) and precipitation summary | `daily_weather` (list of temp/precip dicts), `base_temperature_c` (opt), `upper_cutoff_c` (opt), `dry_day_threshold_mm` (opt) |

---

## 5. Agronomic Calculations & Assumptions

### 1. Growing Degree Days (GDD)
* **Equation:**
  $$\text{Daily GDD} = \max\left(0, \frac{T_{\text{max}} + T_{\text{min}}}{2} - T_{\text{base}}\right)$$
* If an upper cutoff temperature ($T_{\text{cutoff}}$) is supplied, daily temperatures exceeding $T_{\text{cutoff}}$ are capped at $T_{\text{cutoff}}$ prior to averaging.
* **Default Base Temperature:** $10.0^\circ\text{C}$ (typical baseline for warm-season cereals like maize/sorghum; cool-season cereals like teff/wheat may use $4.0^\circ\text{C} - 5.0^\circ\text{C}$).
* **Limitation:** GDD calculations are deterministic thermal indices and must be calibrated to specific local cultivars and elevation zones before guiding planting or harvest decisions.

### 2. Precipitation Summary
* **Cumulative Rainfall:** $\sum \text{precipitation\_mm}$ across the window.
* **Rainy Day Count:** Number of days with rainfall $\ge \text{dry\_day\_threshold\_mm}$ (default $1.0\text{ mm}$).
* **Longest Consecutive Dry Days:** Maximum streak of consecutive days with rainfall $< \text{threshold}$, indicating potential drought stress periods.

---

## 6. Sourced Agricultural Knowledge Base

Knowledge entries in `src/agricultural_assistant/data/crop_knowledge.py` and stored in SQLite are backed by reputable institutions:
* **Ethiopian Institute of Agricultural Research (EIAR):** Maize lethal necrosis, teff rust, coffee berry disease bulletins.
* **FAO & CIMMYT:** Fall armyworm IPM guidelines, stem rust surveillance.
* **CABI Plantwise Knowledge Bank:** Sorghum anthracnose and pest management.
* **Metadata Fields:** Every knowledge record stores `crop_name`, `disease_or_pest`, `symptoms`, `contributing_conditions`, `management_practices`, `source_reference`, `verification_status` (`verified`), and `language` (`en`).
* **Multilingual Schema:** The database schema supports `am` (Amharic), `om` (Afaan Oromo), and `ti` (Tigrinya). Unverified machine translations are never inserted or fabricated.

---

## 7. Backup and Restore Procedure

To back up the SQLite database safely without stopping active read operations:

### Backup:
```bash
# Using SQLite's safe online backup API:
sqlite3 data/agricultural_assistant.db ".backup 'data/backup_$(date +%Y%m%d_%H%M%S).db'"
```

### Restore:
```bash
# 1. Stop any running server or CLI instances
# 2. Overwrite the database file from backup:
cp data/backup_20261020_000000.db data/agricultural_assistant.db
# 3. Clean any existing WAL journal files
rm -f data/agricultural_assistant.db-wal data/agricultural_assistant.db-shm
```

---

## 8. Getting Started & Development

### Prerequisites
* Linux / macOS / Windows WSL
* [`uv`](https://docs.astral.sh/uv/) installed:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
* Python 3.12 (managed automatically by `uv`)

### Installation & Environment Synchronization
```bash
git clone https://github.com/hope/agricultural-mcp-assistant.git
cd agricultural-mcp-assistant

# Synchronize virtual environment with all runtime and development packages
uv sync --extra dev
```

### Running Tests
Execute the complete 102-test automated test suite:
```bash
uv run pytest
```

---

## 9. How to Run the Server and Client

### Option A: Interactive 10-Option CLI Client
The interactive CLI automatically spawns the MCP server as a subprocess over `stdio`, handles handshakes, and provides a menu for all capabilities:
```bash
uv run agricultural-assistant
```
Menu options:
```text
=== AGRICULTURAL MCP ASSISTANT ===
1. Search crop disease / pest diagnosis
2. Get weather forecast (coordinates)
3. Record a farm observation
4. View a farm observation by ID
5. List recent farm observations
6. Count farm observations
7. View farm observation summary insights
8. Calculate agronomic metrics (GDD & Rainfall)
9. Ask assistant (Natural Language / LLM)
10. Exit
```

### Option B: Standalone MCP Server
To run the server directly on `stdio` (for integration with Claude Desktop, MCP Inspector, or other MCP hosts):
```bash
uv run agricultural-assistant-server
```
Or via Python module:
```bash
uv run python -m agricultural_assistant.server.app
```

---

## 10. Known Limitations & Implementation Matrix

| Component | Status | Notes |
| :--- | :--- | :--- |
| **Observation Storage** | **Fully Implemented** | SQLite relational persistence with WAL, transactions, migrations, and repository layer. |
| **Observation Retrieval & Filtering** | **Fully Implemented** | Fetch by ID, pagination, date-range filtering, and crop filtering. |
| **Historical Summary Insights** | **Fully Implemented** | Sample size confidence flags, crop/stage distributions, and symptom keyword mention counts (clearly disclaimed as unverified mentions). |
| **Agronomic Calculations** | **Fully Implemented** | Mathematical GDD and dry/wet spell metrics with documented formulas and hand-calculated test cases. |
| **FTS5 Knowledge Search** | **Fully Implemented** | SQLite FTS5 search with source attribution, duplicate prevention, and reindexing. |
| **Multilingual Knowledge** | **Schema Ready** | Schema and database columns support Amharic, Afaan Oromo, and Tigrinya; content currently seeded in English. No unverified machine translations are fabricated. |
| **Weather Integration** | **Fully Implemented** | Open-Meteo REST integration with mock fallbacks for network-isolated test runs. |
| **Diagnostic Disclaimer** | **Active Policy** | All symptom matching and note aggregations provide advisory disclaimers and do not replace certified agronomist or pathology lab verification. |
# agri-mcp-agent
