"""Fire-and-forget HTTP transport for telemetry events.

Uses ``urllib.request`` rather than ``httpx`` so telemetry works without the
``[cloud]`` extras -- a user who explicitly opts in shouldn't be told to
install another package first.

Two entry points:

- :func:`send` -- fire-and-forget on a daemon thread. The default in
  production code paths. Returns immediately; the caller never observes
  the network at all.
- :func:`send_sync` -- synchronous, blocking. For tests and the dispatcher's
  internal verification path.

Both swallow every exception. The cost of a missed event is zero; the cost
of a hung or crashing CLI is significant.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping

import docglow as _docglow

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 2.0
USER_AGENT = f"docglow-cli-telemetry/{_docglow.__version__}"

ENV_VERCEL_BYPASS = "DOCGLOW_VERCEL_BYPASS"
ENV_DEBUG = "DOCGLOW_TELEMETRY_DEBUG"

# Bounded total wait at process exit, regardless of how many sends are in flight.
# Each individual send still has its own timeout enforced by urlopen.
_ATEXIT_BUDGET_SECONDS = 2.5

_pending_lock = threading.Lock()
_pending_threads: list[threading.Thread] = []
_atexit_registered = False


def _register_atexit_once() -> None:
    global _atexit_registered
    if _atexit_registered:
        return
    atexit.register(_drain_pending)
    _atexit_registered = True


def _drain_pending() -> None:
    """Wait up to ``_ATEXIT_BUDGET_SECONDS`` total for in-flight sends to finish.

    Without this, daemon-thread sends are killed mid-flight when the
    interpreter exits, and POSTs are silently dropped before they reach the
    network. The budget is shared across all pending threads.
    """
    with _pending_lock:
        threads = [t for t in _pending_threads if t.is_alive()]
        _pending_threads.clear()

    if not threads:
        return

    deadline = threading.Event()
    timer = threading.Timer(_ATEXIT_BUDGET_SECONDS, deadline.set)
    timer.daemon = True
    timer.start()
    try:
        for thread in threads:
            if deadline.is_set():
                break
            # join blocks until the thread exits or its own timeout fires;
            # urllib.request.urlopen already enforces a per-request timeout.
            thread.join(timeout=_ATEXIT_BUDGET_SECONDS)
    finally:
        timer.cancel()


def _is_debug(env: Mapping[str, str]) -> bool:
    value = env.get(ENV_DEBUG, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_request(
    payload: dict[str, object],
    endpoint: str,
    env: Mapping[str, str],
) -> urllib.request.Request:
    body = json.dumps(payload).encode("utf-8")
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    bypass = env.get(ENV_VERCEL_BYPASS)
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
        headers["x-vercel-set-bypass-cookie"] = "true"
    return urllib.request.Request(
        url=endpoint,
        data=body,
        headers=headers,
        method="POST",
    )


def send_sync(
    payload: dict[str, object],
    endpoint: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> bool:
    """POST the payload synchronously. Returns True on 2xx, False otherwise.

    Never raises. Exceptions are caught and logged at DEBUG. When
    ``DOCGLOW_TELEMETRY_DEBUG`` is truthy, also emits an INFO line per send
    so users can self-diagnose "why aren't my events showing up?".
    """
    environ = env if env is not None else os.environ
    debug = _is_debug(environ)
    try:
        request = _build_request(payload, endpoint, environ)
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            ok = bool(200 <= response.status < 300)
            if debug:
                logger.info("telemetry: POST %s -> %s", endpoint, response.status)
            return ok
    except urllib.error.HTTPError as exc:
        logger.debug("telemetry: HTTP %s from %s", exc.code, endpoint)
        if debug:
            logger.info("telemetry: POST %s -> %s (HTTPError)", endpoint, exc.code)
        return False
    except Exception as exc:
        logger.debug("telemetry: send failed: %s", exc)
        if debug:
            logger.info("telemetry: POST %s -> failed (%s)", endpoint, exc)
        return False


def send(
    payload: dict[str, object],
    endpoint: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Fire-and-forget: POST on a daemon thread. Never raises, never blocks.

    The thread is daemonised so process shutdown does not wait for it
    indefinitely, but an ``atexit`` hook gives in-flight sends a bounded
    budget to finish so a fast CLI exit doesn't kill the request mid-TLS.
    """
    try:
        thread = threading.Thread(
            target=send_sync,
            args=(payload, endpoint, timeout),
            name="docglow-telemetry",
            daemon=True,
        )
        with _pending_lock:
            _pending_threads.append(thread)
            _register_atexit_once()
        thread.start()
    except Exception as exc:
        # Even thread-creation failures must not propagate.
        logger.debug("telemetry: thread spawn failed: %s", exc)
