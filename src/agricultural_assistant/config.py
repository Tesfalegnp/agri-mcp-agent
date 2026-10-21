"""Configuration module for the Agricultural MCP Assistant.

Loads runtime settings safely from environment variables without exposing
sensitive information or hard-coding secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Automatically load .env if present in workspace root or current directory
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()


class Settings(BaseModel):
    """Application runtime settings and configuration contracts."""

    app_env: Literal["development", "testing", "production"] = Field(
        default="development",
        description="Deployment environment name.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level for stderr output (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        description="Base URL for Open-Meteo weather API.",
    )
    database_path: str = Field(
        default="data/agricultural_assistant.db",
        description="File path for the SQLite database.",
    )
    # Gemini AI Configuration (Phase 7 Primary Provider)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="API key for Google Gemini GenAI requests.",
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash",
        description="Default model name for Gemini tool-calling.",
    )
    gemini_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout for Gemini API requests in seconds.",
    )
    # Backend Web Server Configuration (Phase 7)
    backend_host: str = Field(
        default="127.0.0.1",
        description="Host for the FastAPI HTTP web server.",
    )
    backend_port: int = Field(
        default=8000,
        description="Port for the FastAPI HTTP web server.",
    )
    # OAuth 2.1 Configuration (Phase 5)
    oauth_enforce_remote: bool = Field(
        default=True,
        description="Whether to enforce OAuth 2.1 Bearer authentication on Streamable HTTP /mcp endpoint.",
    )
    oauth_issuer: str = Field(
        default="http://127.0.0.1:8000",
        description="Expected OAuth 2.1 token issuer URL.",
    )
    oauth_resource_url: str = Field(
        default="http://127.0.0.1:8000/mcp",
        description="Expected OAuth 2.1 target resource URI (audience).",
    )
    oauth_secret_key: Optional[str] = Field(
        default=None,
        description="Secret key for signing HMAC-SHA256 OAuth tokens (generated automatically if not set).",
    )
    # MCP Transport Configuration (Phase 4)
    mcp_default_transport: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        description="Initial MCP transport to connect on startup ('stdio' or 'streamable-http').",
    )
    mcp_streamable_url: str = Field(
        default="http://127.0.0.1:8000/mcp",
        description="Streamable HTTP MCP endpoint URL.",
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origins for the frontend.",
    )
    # Legacy / Optional OpenAI Configuration (Kept for Phase 6 backwards compatibility)
    openai_api_key: Optional[str] = Field(
        default=None,
        description="API key for OpenAI API requests.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="Default model name for OpenAI tool-calling.",
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for OpenAI-compatible endpoints.",
    )
    openai_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout for AI API requests in seconds.",
    )
    max_tool_rounds: int = Field(
        default=5,
        description="Maximum model/tool execution rounds per prompt.",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure the log level is a valid standard logging level name."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_val = value.strip().upper()
        if upper_val not in valid_levels:
            raise ValueError(
                f"Invalid log_level '{value}'. Must be one of {sorted(valid_levels)}"
            )
        return upper_val

    def __repr__(self) -> str:
        masked_openai = "***" if self.openai_api_key else "None"
        masked_gemini = "***" if self.gemini_api_key else "None"
        return (
            f"Settings(app_env={self.app_env!r}, log_level={self.log_level!r}, "
            f"open_meteo_base_url={self.open_meteo_base_url!r}, database_path={self.database_path!r}, "
            f"gemini_model={self.gemini_model!r}, gemini_api_key={masked_gemini}, "
            f"openai_model={self.openai_model!r}, openai_api_key={masked_openai}, "
            f"max_tool_rounds={self.max_tool_rounds})"
        )


def get_settings() -> Settings:
    """Instantiate and validate Settings from current environment variables."""
    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"
    openai_base = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("Gemini_api_key")
    gemini_model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

    timeout_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", "30.0")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 30.0

    rounds_raw = os.getenv("MAX_TOOL_ROUNDS", "5")
    try:
        max_rounds = int(rounds_raw)
    except ValueError:
        max_rounds = 5

    port_raw = os.getenv("BACKEND_PORT", "8000")
    try:
        port = int(port_raw)
    except ValueError:
        port = 8000

    cors_raw = os.getenv("CORS_ORIGINS")
    if cors_raw:
        cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
    else:
        cors_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    enforce_remote_raw = os.getenv("OAUTH_ENFORCE_REMOTE", "true").lower()
    oauth_enforce_remote = enforce_remote_raw in ("true", "1", "yes")

    mcp_transport_raw = os.getenv("MCP_DEFAULT_TRANSPORT", "stdio").strip().lower()
    mcp_default_transport: Literal["stdio", "streamable-http"] = (
        "streamable-http" if mcp_transport_raw in ("streamable-http", "http") else "stdio"
    )

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),  # type: ignore[arg-type]
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        open_meteo_base_url=os.getenv(
            "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"
        ),
        database_path=os.getenv("DATABASE_PATH", "data/agricultural_assistant.db"),
        gemini_api_key=gemini_key,
        gemini_model=gemini_model,
        backend_host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        backend_port=port,
        oauth_enforce_remote=oauth_enforce_remote,
        oauth_issuer=os.getenv("OAUTH_ISSUER", "http://127.0.0.1:8000"),
        oauth_resource_url=os.getenv("OAUTH_RESOURCE_URL", "http://127.0.0.1:8000/mcp"),
        oauth_secret_key=os.getenv("OAUTH_SECRET_KEY"),
        mcp_default_transport=mcp_default_transport,
        mcp_streamable_url=os.getenv("MCP_STREAMABLE_URL", "http://127.0.0.1:8000/mcp"),
        cors_origins=cors_origins,
        openai_api_key=openai_key,
        openai_model=openai_model,
        openai_base_url=openai_base,
        openai_timeout_seconds=timeout,
        max_tool_rounds=max_rounds,
    )
