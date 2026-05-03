"""Tests for docglow.telemetry.client.

Uses Python's stdlib http.server rather than pytest-httpserver to avoid
adding a test dep just for this. The server is in a thread so we can
control its behaviour per-test.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from docglow.telemetry import client


def _make_handler(
    on_request: Callable[[dict[str, Any]], tuple[int, bytes]],
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:  # silence
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            status, response_body = on_request(payload)
            self.send_response(status)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    return Handler


class _StubServer:
    def __init__(
        self,
        on_request: Callable[[dict[str, Any]], tuple[int, bytes]] | None = None,
    ) -> None:
        self.received: list[dict[str, Any]] = []
        self._handler_factory = on_request or self._default_handler
        handler_cls = _make_handler(self._record_and_dispatch)
        self.server = HTTPServer(("127.0.0.1", 0), handler_cls)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def _default_handler(self, _payload: dict[str, Any]) -> tuple[int, bytes]:
        return (204, b"")

    def _record_and_dispatch(self, payload: dict[str, Any]) -> tuple[int, bytes]:
        self.received.append(payload)
        return self._handler_factory(payload)

    def __enter__(self) -> _StubServer:
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()


def test_send_sync_204_returns_true() -> None:
    with _StubServer() as stub:
        ok = client.send_sync({"hello": "world"}, stub.url)
    assert ok is True
    assert stub.received == [{"hello": "world"}]


def test_send_sync_500_returns_false_does_not_raise() -> None:
    with _StubServer(on_request=lambda _p: (500, b"server error")) as stub:
        ok = client.send_sync({"x": 1}, stub.url)
    assert ok is False
    # Server still received the request
    assert stub.received == [{"x": 1}]


def test_send_sync_connection_refused_does_not_raise() -> None:
    # 127.0.0.1:1 is reliably refused
    ok = client.send_sync({"x": 1}, "http://127.0.0.1:1/")
    assert ok is False


def test_send_sync_timeout_does_not_raise() -> None:
    def slow_handler(_payload: dict[str, Any]) -> tuple[int, bytes]:
        time.sleep(0.5)
        return (204, b"")

    with _StubServer(on_request=slow_handler) as stub:
        ok = client.send_sync({"x": 1}, stub.url, timeout=0.05)
    assert ok is False


def test_send_sync_invalid_url_does_not_raise() -> None:
    ok = client.send_sync({"x": 1}, "not-a-url")
    assert ok is False


def test_send_sync_includes_user_agent_and_content_type() -> None:
    captured: dict[str, str] = {}

    class CapturingHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            captured["user_agent"] = self.headers.get("User-Agent", "")
            captured["content_type"] = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = HTTPServer(("127.0.0.1", 0), CapturingHandler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client.send_sync({"x": 1}, url)
    finally:
        server.shutdown()
        server.server_close()

    assert captured["content_type"] == "application/json"
    assert captured["user_agent"].startswith("docglow-cli-telemetry/")


def test_send_async_returns_immediately_even_with_slow_server() -> None:
    def slow_handler(_payload: dict[str, Any]) -> tuple[int, bytes]:
        time.sleep(1.0)
        return (204, b"")

    with _StubServer(on_request=slow_handler) as stub:
        start = time.monotonic()
        client.send({"x": 1}, stub.url, timeout=2.0)
        elapsed = time.monotonic() - start

    # Caller should not block on the slow server. 200ms is generous; in
    # practice this is < 10ms.
    assert elapsed < 0.2, f"send() blocked for {elapsed:.3f}s"


def test_send_async_does_not_raise_on_bad_endpoint() -> None:
    # Should not raise even when the endpoint is unreachable
    client.send({"x": 1}, "http://127.0.0.1:1/")


def test_send_async_eventually_delivers(tmp_path: Any) -> None:
    with _StubServer() as stub:
        client.send({"x": 1}, stub.url, timeout=2.0)
        # Allow a moment for the daemon thread to complete the request
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not stub.received:
            time.sleep(0.02)

    assert stub.received == [{"x": 1}]


@pytest.mark.parametrize("status", [400, 404, 413, 429, 500, 503])
def test_send_sync_non_2xx_returns_false(status: int) -> None:
    with _StubServer(on_request=lambda _p: (status, b"")) as stub:
        ok = client.send_sync({"x": 1}, stub.url)
    assert ok is False


def _capture_headers() -> tuple[str, dict[str, str], Callable[[], None]]:
    captured: dict[str, str] = {}

    class CapturingHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            for name in (
                "x-vercel-protection-bypass",
                "x-vercel-set-bypass-cookie",
                "User-Agent",
                "Content-Type",
            ):
                value = self.headers.get(name)
                if value is not None:
                    captured[name] = value
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = HTTPServer(("127.0.0.1", 0), CapturingHandler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def shutdown() -> None:
        server.shutdown()
        server.server_close()

    return url, captured, shutdown


def test_send_sync_attaches_vercel_bypass_headers_when_env_set() -> None:
    url, captured, shutdown = _capture_headers()
    try:
        client.send_sync(
            {"x": 1},
            url,
            env={"DOCGLOW_VERCEL_BYPASS": "secret-token"},
        )
    finally:
        shutdown()

    assert captured.get("x-vercel-protection-bypass") == "secret-token"
    assert captured.get("x-vercel-set-bypass-cookie") == "true"


def test_send_sync_omits_vercel_bypass_headers_when_env_unset() -> None:
    url, captured, shutdown = _capture_headers()
    try:
        client.send_sync({"x": 1}, url, env={})
    finally:
        shutdown()

    assert "x-vercel-protection-bypass" not in captured
    assert "x-vercel-set-bypass-cookie" not in captured


def test_send_sync_emits_info_log_when_debug_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with _StubServer() as stub:
        with caplog.at_level("INFO", logger="docglow.telemetry.client"):
            client.send_sync(
                {"x": 1},
                stub.url,
                env={"DOCGLOW_TELEMETRY_DEBUG": "1"},
            )

    info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert any("telemetry: POST" in m and "204" in m for m in info_messages)


def test_send_sync_silent_when_debug_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with _StubServer() as stub:
        with caplog.at_level("INFO", logger="docglow.telemetry.client"):
            client.send_sync({"x": 1}, stub.url, env={})

    info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert info_messages == []


def test_send_sync_debug_log_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("INFO", logger="docglow.telemetry.client"):
        client.send_sync(
            {"x": 1},
            "http://127.0.0.1:1/",
            env={"DOCGLOW_TELEMETRY_DEBUG": "1"},
        )

    info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert any("failed" in m for m in info_messages)


def test_drain_pending_completes_in_flight_sends() -> None:
    """An in-flight send launched via send() must complete when _drain_pending runs.

    Regression: without atexit drain, the daemon thread is killed at process
    exit and the POST never reaches the server. We simulate process exit by
    invoking _drain_pending() directly after send().
    """

    def slow_handler(_payload: dict[str, Any]) -> tuple[int, bytes]:
        # Long enough to ensure the request would not finish before
        # send() returns, but well within the drain budget.
        time.sleep(0.3)
        return (204, b"")

    with _StubServer(on_request=slow_handler) as stub:
        # Reset module state so this test is hermetic.
        with client._pending_lock:
            client._pending_threads.clear()
        client.send({"x": 1}, stub.url, timeout=2.0)
        # Simulate process exit.
        client._drain_pending()

    assert stub.received == [{"x": 1}]
