"""End-to-end test: opt-in flow against a stub HTTP server.

Exercises the full chain CLI -> dispatcher -> client -> network. The
generate command is patched at the generate_site boundary (the heavy lift
is not what we're testing), but every layer of telemetry is real.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docglow import cloud_hint
from docglow.cli import cli
from docglow.telemetry import state
from docglow.telemetry.config import TelemetryConfig


class _CapturingServer:
    """Thread-backed HTTP server that records POST bodies."""

    def __init__(self, response_status: int = 204) -> None:
        self.received: list[dict[str, Any]] = []
        self.response_status = response_status
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:
                    payload = {"_raw": body.decode("utf-8", "replace")}
                outer.received.append(payload)
                self.send_response(outer.response_status)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/telemetry/events"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> _CapturingServer:
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()


def _wait_for_event(stub: _CapturingServer, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not stub.received:
        time.sleep(0.02)


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state_path = tmp_path / "telemetry.json"
    monkeypatch.setattr(state, "_state_path", lambda: state_path)
    cloud_hint_state = tmp_path / "cloud_hint.json"
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: cloud_hint_state)
    monkeypatch.setenv("DOCGLOW_NO_CLOUD_HINT", "1")
    monkeypatch.delenv("DOCGLOW_TELEMETRY", raising=False)
    monkeypatch.delenv("DOCGLOW_NO_TELEMETRY", raising=False)
    monkeypatch.delenv("CI", raising=False)
    return state_path


def _mock_config(endpoint: str, *, enabled: bool) -> MagicMock:
    config = MagicMock()
    config.ai.enabled = False
    config.title = "docglow"
    config.slim = False
    config.column_lineage = True
    config.telemetry = TelemetryConfig(enabled=enabled, endpoint=endpoint)
    return config


def test_e2e_enabled_generates_one_event(tmp_path: Path) -> None:
    runner = CliRunner()
    with _CapturingServer() as stub:
        with (
            patch(
                "docglow.config.load_config",
                return_value=_mock_config(stub.url, enabled=True),
            ),
            patch(
                "docglow.generator.site.generate_site",
                return_value=(tmp_path / "output", 85.0),
            ),
        ):
            result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        _wait_for_event(stub)

    assert len(stub.received) == 1
    event = stub.received[0]
    assert event["command"] == "generate"
    assert event["result"] == "success"
    assert event["schema_version"] == 1
    assert "instance_id" in event
    assert "duration_ms" in event


def test_e2e_disabled_sends_no_event(tmp_path: Path) -> None:
    runner = CliRunner()
    with _CapturingServer() as stub:
        with (
            patch(
                "docglow.config.load_config",
                return_value=_mock_config(stub.url, enabled=False),
            ),
            patch(
                "docglow.generator.site.generate_site",
                return_value=(tmp_path / "output", 85.0),
            ),
        ):
            result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        # Wait briefly to be sure no event arrives late
        time.sleep(0.2)

    assert stub.received == []


def test_e2e_server_500_does_not_break_generate(tmp_path: Path) -> None:
    """Telemetry server failure must not affect the user's exit code."""
    runner = CliRunner()
    with _CapturingServer(response_status=500) as stub:
        with (
            patch(
                "docglow.config.load_config",
                return_value=_mock_config(stub.url, enabled=True),
            ),
            patch(
                "docglow.generator.site.generate_site",
                return_value=(tmp_path / "output", 85.0),
            ),
        ):
            result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

        _wait_for_event(stub)

    # Generate succeeded even though the server rejected the event
    assert result.exit_code == 0, result.output
    # Server still received the attempt
    assert len(stub.received) == 1


def test_e2e_unreachable_endpoint_does_not_break_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Endpoint completely unreachable must not affect the user's exit code."""
    unreachable = "http://127.0.0.1:1/v1/telemetry/events"
    runner = CliRunner()
    with (
        patch(
            "docglow.config.load_config",
            return_value=_mock_config(unreachable, enabled=True),
        ),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 85.0),
        ),
    ):
        result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_e2e_consent_yes_in_state_file_activates_send(tmp_path: Path, isolated: Path) -> None:
    """User who ran `docglow telemetry enable` should see telemetry fire even
    when no env vars or yml flag is set.
    """
    state.set_consent("yes", isolated)

    runner = CliRunner()
    with _CapturingServer() as stub:
        with (
            patch(
                "docglow.config.load_config",
                return_value=_mock_config(stub.url, enabled=False),
            ),
            patch(
                "docglow.generator.site.generate_site",
                return_value=(tmp_path / "output", 85.0),
            ),
        ):
            result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0, result.output
        _wait_for_event(stub)

    assert len(stub.received) == 1
