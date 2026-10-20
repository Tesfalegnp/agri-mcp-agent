"""Unit tests for application configuration and logging setup."""

from __future__ import annotations

import logging
import os
import sys

import pytest
from pydantic import ValidationError

from agricultural_assistant.config import Settings, get_settings
from agricultural_assistant.logging_config import configure_logging


class TestConfiguration:
    """Test suite for Settings model and environment variable handling."""

    def test_default_settings(self) -> None:
        """Verify default settings values when no environment variables are set."""
        settings = Settings()
        assert settings.app_env == "development"
        assert settings.log_level == "INFO"
        assert settings.open_meteo_base_url == "https://api.open-meteo.com/v1/forecast"

    def test_custom_settings_via_model(self) -> None:
        """Verify custom values pass validation."""
        settings = Settings(
            app_env="production",
            log_level="warning",
            open_meteo_base_url="https://custom-weather.example.com",
        )
        assert settings.app_env == "production"
        assert settings.log_level == "WARNING"  # normalized to uppercase
        assert settings.open_meteo_base_url == "https://custom-weather.example.com"

    def test_invalid_log_level(self) -> None:
        """Verify invalid log level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(log_level="VERBOSE")
        assert "log_level" in str(exc_info.value)

    def test_get_settings_reads_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify get_settings() correctly ingests environment variables."""
        monkeypatch.setenv("APP_ENV", "testing")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        settings = get_settings()
        assert settings.app_env == "testing"
        assert settings.log_level == "DEBUG"

    def test_openai_settings_loading_and_secret_masking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify OpenAI settings load properly and secrets are masked in repr."""
        secret = "sk-test-secret-key-12345"
        monkeypatch.setenv("OPENAI_API_KEY", secret)
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        monkeypatch.setenv("MAX_TOOL_ROUNDS", "7")
        monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "45.0")

        settings = get_settings()
        assert settings.openai_api_key == secret
        assert settings.openai_model == "gpt-4o"
        assert settings.max_tool_rounds == 7
        assert settings.openai_timeout_seconds == 45.0

        # Verify repr does not leak secret key
        repr_str = repr(settings)
        assert secret not in repr_str
        assert "***" in repr_str


class TestLoggingConfiguration:
    """Test suite for logging configuration and stdio safety."""

    def test_logging_handler_outputs_to_stderr(self) -> None:
        """Verify that logging handlers target sys.stderr rather than stdout.

        This is vital for stdio-based MCP servers to avoid stream corruption.
        """
        logger = configure_logging("DEBUG")
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) >= 1

        # Check that at least one stream handler writes to stderr
        stream_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) >= 1
        assert any(h.stream is sys.stderr for h in stream_handlers)
