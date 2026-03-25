"""MCP server orchestrator.

Loads dbt artifacts, builds the docglow data layer, and serves
MCP tool calls over stdio JSON-RPC.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from docglow import __version__
from docglow.mcp.tools import TOOL_MAP, TOOLS
from docglow.mcp.transport import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    TransportError,
    make_error,
    make_response,
    read_message,
    write_message,
)

logger = logging.getLogger(__name__)

# MCP protocol version we support
PROTOCOL_VERSION = "2024-11-05"

SERVER_INFO = {
    "name": "docglow",
    "version": __version__,
}


def _build_tools_list() -> list[dict[str, Any]]:
    """Build the tools/list response payload."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }
        for tool in TOOLS
    ]


def _handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    """Handle the initialize request."""
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
        },
        "serverInfo": SERVER_INFO,
    }


def _handle_tools_list() -> dict[str, Any]:
    """Handle tools/list request."""
    return {"tools": _build_tools_list()}


def _handle_tools_call(
    data: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle tools/call request."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    tool = TOOL_MAP.get(tool_name)
    if not tool:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Unknown tool: {tool_name}",
                }
            ],
            "isError": True,
        }

    try:
        result = tool.handler(data, arguments)
    except Exception as e:
        logger.exception("Tool %s raised an exception", tool_name)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Tool error: {e}",
                }
            ],
            "isError": True,
        }

    # MCP tools return content blocks
    import json

    text = json.dumps(result, indent=2, default=str)
    return {
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }


def run_server(project_dir: Path, target_dir: Path | None = None) -> None:
    """Run the MCP server on stdio.

    Loads artifacts once, then enters the message loop.
    Logs go to stderr (stdout is reserved for JSON-RPC).
    """
    # Configure logging to stderr
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s - %(message)s",
        stream=sys.stderr,
    )

    logger.info("Loading dbt artifacts from %s", project_dir)

    from docglow.artifacts.loader import ArtifactLoadError, load_artifacts
    from docglow.generator.data import build_docglow_data

    try:
        artifacts = load_artifacts(project_dir, target_dir)
    except ArtifactLoadError as e:
        logger.error("Failed to load artifacts: %s", e)
        sys.exit(1)

    data = build_docglow_data(artifacts)
    model_count = len(data["models"])
    source_count = len(data["sources"])
    logger.info("Data loaded: %d models, %d sources", model_count, source_count)

    logger.info("MCP server ready on stdio")

    # Message loop
    initialized = False
    while True:
        try:
            msg = read_message()
        except TransportError as e:
            logger.error("Transport error: %s", e)
            continue

        if msg is None:
            logger.info("EOF received, shutting down")
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        logger.debug("Received: %s (id=%s)", method, msg_id)

        # Notifications (no id) — just acknowledge
        if method == "notifications/initialized":
            initialized = True
            continue

        if method == "initialize":
            response = make_response(msg_id, _handle_initialize(params))

        elif method == "tools/list":
            if not initialized:
                response = make_error(
                    msg_id,
                    INVALID_PARAMS,
                    "Server not yet initialized",
                )
            else:
                response = make_response(msg_id, _handle_tools_list())

        elif method == "tools/call":
            if not initialized:
                response = make_error(
                    msg_id,
                    INVALID_PARAMS,
                    "Server not yet initialized",
                )
            else:
                result = _handle_tools_call(data, params)
                response = make_response(msg_id, result)

        elif method == "ping":
            response = make_response(msg_id, {})

        else:
            response = make_error(
                msg_id,
                METHOD_NOT_FOUND,
                f"Unknown method: {method}",
            )

        write_message(response)
