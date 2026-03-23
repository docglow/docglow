"""Tests for MCP transport layer."""

from __future__ import annotations

import io
import json

import pytest

from docglow.mcp.transport import (
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    TransportError,
    make_error,
    make_response,
    read_message,
    write_message,
)


def _frame_message(msg: dict) -> bytes:
    """Frame a JSON message with Content-Length header."""
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()
    return header + body


class TestReadMessage:
    def test_reads_valid_message(self) -> None:
        msg = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
        stream = io.BytesIO(_frame_message(msg))
        result = read_message(stream)
        assert result == msg

    def test_returns_none_on_eof(self) -> None:
        stream = io.BytesIO(b"")
        result = read_message(stream)
        assert result is None

    def test_raises_on_missing_content_length(self) -> None:
        stream = io.BytesIO(b"\r\n{}")
        with pytest.raises(TransportError, match="Missing Content-Length"):
            read_message(stream)

    def test_raises_on_invalid_content_length(self) -> None:
        stream = io.BytesIO(b"Content-Length: abc\r\n\r\n{}")
        with pytest.raises(TransportError, match="Invalid Content-Length"):
            read_message(stream)

    def test_raises_on_invalid_json(self) -> None:
        body = b"not json"
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        stream = io.BytesIO(header + body)
        with pytest.raises(TransportError, match="Invalid JSON"):
            read_message(stream)

    def test_reads_multiple_messages(self) -> None:
        msg1 = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
        msg2 = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
        stream = io.BytesIO(_frame_message(msg1) + _frame_message(msg2))

        assert read_message(stream) == msg1
        assert read_message(stream) == msg2
        assert read_message(stream) is None


class TestWriteMessage:
    def test_writes_framed_message(self) -> None:
        msg = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        stream = io.BytesIO()
        write_message(msg, stream)

        stream.seek(0)
        output = stream.read()
        # Parse it back
        header_end = output.index(b"\r\n\r\n") + 4
        body = output[header_end:]
        assert json.loads(body) == msg


class TestMakeResponse:
    def test_basic_response(self) -> None:
        resp = make_response(1, {"tools": []})
        assert resp == {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}


class TestMakeError:
    def test_basic_error(self) -> None:
        resp = make_error(1, METHOD_NOT_FOUND, "Not found")
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        assert resp["error"]["message"] == "Not found"

    def test_error_with_data(self) -> None:
        resp = make_error(1, INTERNAL_ERROR, "Oops", data={"detail": "stack"})
        assert resp["error"]["data"] == {"detail": "stack"}
