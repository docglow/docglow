"""Integration tests for the MCP server message handling."""

from __future__ import annotations

import io
import json

import pytest

from docglow.mcp.server import (
    PROTOCOL_VERSION,
    _handle_initialize,
    _handle_tools_call,
    _handle_tools_list,
)
from docglow.mcp.transport import read_message


@pytest.fixture()
def sample_data() -> dict:
    """Minimal data for server tests."""
    return {
        "models": {
            "model.test.my_model": {
                "unique_id": "model.test.my_model",
                "name": "my_model",
                "description": "Test model",
                "schema": "public",
                "database": "db",
                "materialization": "table",
                "tags": ["test"],
                "meta": {},
                "path": "models/my_model.sql",
                "folder": "models",
                "raw_sql": "SELECT 1",
                "compiled_sql": "SELECT 1",
                "columns": [],
                "depends_on": [],
                "referenced_by": [],
                "sources_used": [],
                "test_results": [],
                "last_run": None,
                "catalog_stats": {},
                "is_package": False,
            }
        },
        "sources": {},
        "seeds": {},
        "snapshots": {},
        "exposures": {},
        "metrics": {},
        "health": {
            "score": {
                "overall": 50.0,
                "grade": "D",
                "documentation": 0,
                "testing": 0,
                "freshness": 100,
                "complexity": 100,
                "naming": 50,
                "orphans": 0,
            },
            "coverage": {},
            "complexity": {},
            "naming": {},
            "orphans": [],
        },
        "search_index": [],
        "lineage": {"nodes": [], "edges": []},
    }


class TestInitialize:
    def test_returns_protocol_version(self) -> None:
        result = _handle_initialize({})
        assert result["protocolVersion"] == PROTOCOL_VERSION

    def test_returns_server_info(self) -> None:
        result = _handle_initialize({})
        assert result["serverInfo"]["name"] == "docglow"

    def test_advertises_tools_capability(self) -> None:
        result = _handle_initialize({})
        assert "tools" in result["capabilities"]


class TestToolsList:
    def test_returns_all_tools(self) -> None:
        result = _handle_tools_list()
        assert len(result["tools"]) == 9
        names = {t["name"] for t in result["tools"]}
        assert "list_models" in names
        assert "get_model" in names
        assert "search" in names

    def test_tools_have_required_fields(self) -> None:
        result = _handle_tools_list()
        for tool in result["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool


class TestToolsCall:
    def test_call_list_models(self, sample_data: dict) -> None:
        result = _handle_tools_call(sample_data, {"name": "list_models", "arguments": {}})
        assert "content" in result
        assert result["content"][0]["type"] == "text"
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["count"] == 1

    def test_call_unknown_tool(self, sample_data: dict) -> None:
        result = _handle_tools_call(sample_data, {"name": "nonexistent", "arguments": {}})
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_call_search(self, sample_data: dict) -> None:
        result = _handle_tools_call(
            sample_data, {"name": "search", "arguments": {"query": "my_model"}}
        )
        assert "isError" not in result
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["results"][0]["name"] == "my_model"

    def test_tool_error_handling(self, sample_data: dict) -> None:
        """Tools that raise exceptions return isError."""
        # Trigger an error by passing bad data
        bad_data: dict = {"models": None}  # Will cause TypeError in list_models
        result = _handle_tools_call(bad_data, {"name": "list_models", "arguments": {}})
        assert result["isError"] is True


class TestFullSession:
    """Simulate a complete MCP session over the transport."""

    def test_initialize_and_query(self, sample_data: dict) -> None:
        """Simulate: initialize -> tools/list -> tools/call -> EOF."""
        from docglow.mcp.server import (
            _handle_initialize,
            _handle_tools_call,
            _handle_tools_list,
        )
        from docglow.mcp.transport import make_response

        # Build a sequence of messages
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_health", "arguments": {}},
            },
        ]

        # Frame all messages into a single stream
        stream_data = b""
        for msg in messages:
            body = json.dumps(msg).encode("utf-8")
            stream_data += f"Content-Length: {len(body)}\r\n\r\n".encode() + body

        input_stream = io.BytesIO(stream_data)

        # Read and process each message
        responses = []
        for _ in range(len(messages)):
            msg = read_message(input_stream)
            if msg is None:
                break

            method = msg.get("method", "")
            msg_id = msg.get("id")
            params = msg.get("params", {})

            if method == "notifications/initialized":
                continue  # No response for notifications

            if method == "initialize":
                responses.append(make_response(msg_id, _handle_initialize(params)))
            elif method == "tools/list":
                responses.append(make_response(msg_id, _handle_tools_list()))
            elif method == "tools/call":
                responses.append(make_response(msg_id, _handle_tools_call(sample_data, params)))

        assert len(responses) == 3

        # Check initialize response
        assert responses[0]["id"] == 1
        assert responses[0]["result"]["protocolVersion"] == PROTOCOL_VERSION

        # Check tools/list response
        assert responses[1]["id"] == 2
        assert len(responses[1]["result"]["tools"]) == 9

        # Check tools/call response
        assert responses[2]["id"] == 3
        health_text = responses[2]["result"]["content"][0]["text"]
        health = json.loads(health_text)
        assert health["score"]["overall"] == 50.0
