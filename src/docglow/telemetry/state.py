"""Persistent telemetry state: anonymous instance ID and consent.

State file lives at ``click.get_app_dir("docglow")/telemetry.json`` and stores
a stable UUID4 plus a tri-state consent flag. All read/write paths swallow
exceptions -- a corrupt or unwritable state file must never break a CLI
command.

State payload v1::

    {
        "version": 1,
        "instance_id": "<uuid4>",
        "consent": "yes" | "no" | "unset",
        "consent_recorded_at": "<iso8601>"  # only set when consent is yes/no
    }

Mirrors the discipline of :mod:`docglow.cloud_hint`.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import click

STATE_FILENAME = "telemetry.json"
STATE_VERSION = 1

ConsentValue = Literal["yes", "no", "unset"]
_VALID_CONSENT: tuple[ConsentValue, ...] = ("yes", "no", "unset")


def _state_path() -> Path:
    """Return the path to the telemetry state file. Factored for test monkeypatching."""
    return Path(click.get_app_dir("docglow")) / STATE_FILENAME


def _read_payload(path: Path) -> dict[str, object]:
    """Return the validated state payload, or an empty dict on missing/corrupt input."""
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return {}
        if payload.get("version") != STATE_VERSION:
            return {}
        return payload
    except Exception:
        return {}


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist a state payload. Swallows all exceptions."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        # Best-effort: a failed write means we may regenerate the instance_id
        # next call or fail to record consent. Both are acceptable degradations.
        pass


def _is_valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _normalize_consent(value: object) -> ConsentValue:
    if value == "yes":
        return "yes"
    if value == "no":
        return "no"
    return "unset"


def _build_payload(
    instance_id: str, consent: ConsentValue, recorded_at: str | None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": STATE_VERSION,
        "instance_id": instance_id,
        "consent": consent,
    }
    if recorded_at is not None:
        payload["consent_recorded_at"] = recorded_at
    return payload


def get_instance_id(path: Path | None = None) -> str:
    """Return the persisted UUID4, generating and persisting one if absent.

    Always returns a valid UUID4 string. If persistence fails, returns a fresh
    UUID this call (subsequent calls may regenerate -- acceptable since failed
    writes already mean we have no durable state).
    """
    target = path or _state_path()
    payload = _read_payload(target)
    existing = payload.get("instance_id")
    if _is_valid_uuid(existing):
        return existing  # type: ignore[return-value]

    fresh = str(uuid.uuid4())
    consent = _normalize_consent(payload.get("consent"))
    recorded_at = payload.get("consent_recorded_at")
    if not isinstance(recorded_at, str):
        recorded_at = None
    _write_payload(target, _build_payload(fresh, consent, recorded_at))
    return fresh


def get_consent(path: Path | None = None) -> ConsentValue:
    """Return the recorded consent value, or 'unset' if none/invalid."""
    target = path or _state_path()
    payload = _read_payload(target)
    return _normalize_consent(payload.get("consent"))


def set_consent(consent: ConsentValue, path: Path | None = None) -> None:
    """Record consent. Preserves instance_id if present, generates one if not."""
    if consent not in _VALID_CONSENT:
        raise ValueError(f"consent must be one of {_VALID_CONSENT}, got {consent!r}")
    target = path or _state_path()
    payload = _read_payload(target)
    instance_id = payload.get("instance_id")
    if not _is_valid_uuid(instance_id):
        instance_id = str(uuid.uuid4())
    recorded_at = datetime.now(timezone.utc).isoformat() if consent != "unset" else None
    _write_payload(target, _build_payload(instance_id, consent, recorded_at))  # type: ignore[arg-type]
