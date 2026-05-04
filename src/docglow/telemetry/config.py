"""Telemetry configuration and env-var precedence resolution.

Resolution order (highest precedence wins):

    1. ``DOCGLOW_NO_TELEMETRY=1``  - force off, beats everything
    2. ``DOCGLOW_TELEMETRY=1`` / ``DOCGLOW_TELEMETRY=0``
    3. ``docglow.yml`` ``telemetry.enabled``
    4. Default: ``False``

This precedence is part of the user-facing privacy contract documented in
``docs/telemetry.md`` -- changes here must be reflected there.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://api.docglow.com/v1/telemetry/events"

# http:// is permitted only for these hosts (test/dev). Everything else must
# use https:// so payloads aren't sent over plaintext to a misconfigured or
# attacker-supplied endpoint. Silent fallback to DEFAULT_ENDPOINT preserves
# the never-break-CLI invariant.
_HTTP_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}

ENV_OPT_IN = "DOCGLOW_TELEMETRY"
ENV_OPT_OUT = "DOCGLOW_NO_TELEMETRY"
ENV_ENDPOINT_OVERRIDE = "DOCGLOW_TELEMETRY_ENDPOINT"

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class TelemetryConfig:
    """Resolved telemetry configuration.

    ``enabled`` reflects the final answer after applying env-var precedence to
    the yml flag. Components that need to know "should I send a payload?"
    consult this single boolean and do not re-evaluate env vars.
    """

    enabled: bool = False
    endpoint: str = DEFAULT_ENDPOINT


def _parse_tristate(value: str | None) -> bool | None:
    """Return True/False for an env var, or None when unset/unrecognised."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return None


def resolve_telemetry_config(
    raw: dict[str, Any] | None,
    env: Mapping[str, str] | None = None,
) -> TelemetryConfig:
    """Resolve final telemetry config from yml + env vars.

    ``raw`` is the ``telemetry`` section of ``docglow.yml`` (or ``None``).
    ``env`` defaults to ``os.environ``; injectable for tests.
    """
    environ = env if env is not None else os.environ

    if _parse_tristate(environ.get(ENV_OPT_OUT)) is True:
        return TelemetryConfig(enabled=False, endpoint=_resolve_endpoint(raw, environ))

    env_opt_in = _parse_tristate(environ.get(ENV_OPT_IN))
    if env_opt_in is not None:
        return TelemetryConfig(enabled=env_opt_in, endpoint=_resolve_endpoint(raw, environ))

    yml_enabled = bool(raw.get("enabled", False)) if isinstance(raw, dict) else False
    return TelemetryConfig(enabled=yml_enabled, endpoint=_resolve_endpoint(raw, environ))


def _is_safe_endpoint(endpoint: str) -> bool:
    """Return True iff ``endpoint`` is HTTPS, or HTTP to an allowed local host.

    Plaintext HTTP to remote hosts is rejected so a misconfigured yml or env
    var can't route payloads (and any ``DOCGLOW_VERCEL_BYPASS`` token) over
    an unencrypted channel.
    """
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        return False
    if parsed.scheme == "https":
        return bool(parsed.hostname)
    if parsed.scheme == "http":
        return parsed.hostname in _HTTP_ALLOWED_HOSTS
    return False


def _resolve_endpoint(raw: dict[str, Any] | None, env: Mapping[str, str]) -> str:
    """Resolve the endpoint: env override > yml > default.

    Rejects non-HTTPS endpoints (except http://localhost) by silently falling
    back to ``DEFAULT_ENDPOINT``. The user has opted in by configuring an
    override at all, but we don't honor an override that downgrades transport.
    """
    override = env.get(ENV_ENDPOINT_OVERRIDE)
    if override:
        if _is_safe_endpoint(override):
            return override
        logger.debug(
            "telemetry: rejecting non-HTTPS endpoint override %r; falling back to default",
            override,
        )
    if isinstance(raw, dict):
        endpoint = raw.get("endpoint")
        if isinstance(endpoint, str) and endpoint:
            if _is_safe_endpoint(endpoint):
                return endpoint
            logger.debug(
                "telemetry: rejecting non-HTTPS endpoint from yml %r; falling back to default",
                endpoint,
            )
    return DEFAULT_ENDPOINT
