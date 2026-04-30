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

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_ENDPOINT = "https://api.docglow.dev/v1/telemetry/events"

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


def _resolve_endpoint(raw: dict[str, Any] | None, env: Mapping[str, str]) -> str:
    """Resolve the endpoint: env override > yml > default."""
    override = env.get(ENV_ENDPOINT_OVERRIDE)
    if override:
        return override
    if isinstance(raw, dict):
        endpoint = raw.get("endpoint")
        if isinstance(endpoint, str) and endpoint:
            return endpoint
    return DEFAULT_ENDPOINT
