"""Logging configuration module.

CRITICAL STDIO NOTICE:
In a Model Context Protocol (MCP) server running over the 'stdio' transport,
standard output (stdout) is reserved strictly for JSON-RPC protocol messages.
Printing or logging to stdout will corrupt the JSON-RPC message stream and
cause MCP client communication failures.

All application, diagnostic, and audit logs MUST be directed to sys.stderr
or an external log file.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional


def configure_logging(level_name: Optional[str] = "INFO") -> logging.Logger:
    """Configure and return the root package logger directing output to stderr.

    Args:
        level_name: Log level string (e.g. 'DEBUG', 'INFO', 'WARNING').

    Returns:
        Configured logger instance.
    """
    numeric_level = getattr(logging, (level_name or "INFO").upper(), logging.INFO)

    logger = logging.getLogger("agricultural_assistant")
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
