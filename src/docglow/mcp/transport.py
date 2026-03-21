"""Stdio-based JSON-RPC 2.0 transport for MCP."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

# MCP uses Content-Length framed messages over stdio (same as LSP)
_HEADER_CONTENT_LENGTH = "Content-Length"


class TransportError(Exception):
    """Raised when the transport encounters an unrecoverable error."""


def read_message(stream: Any = None) -> dict[str, Any] | None:
    """Read a single JSON-RPC message from stdin.

    Messages are framed with Content-Length headers (LSP/MCP style):
        Content-Length: 123\\r\\n
        \\r\\n
        {json body}

    Returns None on EOF.
    """
    input_stream = stream or sys.stdin.buffer

    # Read headers
    content_length = -1
    while True:
        line = input_stream.readline()
        if not line:
            return None  # EOF

        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
        line_str = line_str.strip()

        if not line_str:
            # Empty line = end of headers
            break

        if line_str.startswith(_HEADER_CONTENT_LENGTH):
            try:
                content_length = int(line_str.split(":", 1)[1].strip())
            except (ValueError, IndexError) as e:
                raise TransportError(f"Invalid Content-Length header: {line_str}") from e

    if content_length < 0:
        raise TransportError("Missing Content-Length header")

    # Read body
    body = input_stream.read(content_length)
    if len(body) < content_length:
        return None  # EOF mid-message

    body_str = body.decode("utf-8") if isinstance(body, bytes) else body

    try:
        return json.loads(body_str)
    except json.JSONDecodeError as e:
        raise TransportError(f"Invalid JSON in message body: {e}") from e


def write_message(msg: dict[str, Any], stream: Any = None) -> None:
    """Write a JSON-RPC message to stdout with Content-Length framing."""
    output_stream = stream or sys.stdout.buffer

    body = json.dumps(msg, separators=(",", ":"))
    body_bytes = body.encode("utf-8")

    header = f"{_HEADER_CONTENT_LENGTH}: {len(body_bytes)}\r\n\r\n"
    header_bytes = header.encode("utf-8")

    output_stream.write(header_bytes)
    output_stream.write(body_bytes)
    output_stream.flush()


def make_response(id: int | str | None, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(
    id: int | str | None,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    """Build a JSON-RPC error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
