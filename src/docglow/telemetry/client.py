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
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

import docglow as _docglow

logger = logging.getLogger(__name__)


class _PostPreservingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow 301/302/303/307/308 redirects while preserving POST body and headers.

    The stdlib default raises ``HTTPError`` on POST + 307/308 -- which is
    technically more conservative than RFC 7231 requires and breaks against
    Vercel routes that issue 307s for host/path canonicalization. Mirrors
    httpx's ``follow_redirects=True`` behaviour used by the cloud client.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if code not in (301, 302, 303, 307, 308):
            return None
        # 303 always degrades to GET per RFC. 301/302/307/308 keep the method
        # (some clients downgrade 301/302 POST -> GET, but Vercel and modern
        # tooling preserve method; we follow that convention).
        new_method = "GET" if code == 303 else req.get_method()
        new_data = None if new_method == "GET" else req.data
        new_headers = {k: v for k, v in req.header_items() if k.lower() != "host"}
        if _is_debug(os.environ):
            _diag(
                f"telemetry: redirect {code} {req.get_method()} {req.full_url} "
                f"-> {new_method} {newurl}"
            )
        return urllib.request.Request(
            newurl,
            data=new_data,
            headers=new_headers,
            origin_req_host=req.origin_req_host,
            unverifiable=True,
            method=new_method,
        )


_opener = urllib.request.build_opener(_PostPreservingRedirectHandler())

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


def _diag(message: str) -> None:
    """Write a debug-mode diagnostic to stderr, bypassing any logging config.

    The ``logger.info()`` path is unreliable across CLI commands because
    different commands configure docglow's loggers at different levels.
    Users who set ``DOCGLOW_TELEMETRY_DEBUG=1`` have explicitly asked to see
    these lines; print them directly so visibility doesn't depend on which
    subcommand happened to bump the log level.
    """
    try:
        print(message, file=sys.stderr, flush=True)
    except Exception:
        # Even a closed stderr must not propagate.
        pass


def send_sync(
    payload: dict[str, object],
    endpoint: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> bool:
    """POST the payload synchronously. Returns True on 2xx, False otherwise.

    Never raises. Exceptions are caught and logged at DEBUG. When
    ``DOCGLOW_TELEMETRY_DEBUG`` is truthy, also writes a one-line diagnostic
    to stderr per send so users can self-diagnose "why aren't my events
    showing up?".
    """
    environ = env if env is not None else os.environ
    debug = _is_debug(environ)
    try:
        request = _build_request(payload, endpoint, environ)
        with _opener.open(request, timeout=timeout) as response:  # noqa: S310
            ok = bool(200 <= response.status < 300)
            if debug:
                _diag(f"telemetry: POST {endpoint} -> {response.status}")
            return ok
    except urllib.error.HTTPError as exc:
        logger.debug("telemetry: HTTP %s from %s", exc.code, endpoint)
        if debug:
            _diag(f"telemetry: POST {endpoint} -> {exc.code} (HTTPError)")
        return False
    except Exception as exc:
        logger.debug("telemetry: send failed: %s", exc)
        if debug:
            _diag(f"telemetry: POST {endpoint} -> failed ({exc})")
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
