"""Non-intrusive Docglow Cloud hint shown after `docglow generate`.

Suppression precedence (highest wins):
    1. DOCGLOW_NO_CLOUD_HINT=1 env var
    2. CI=true env var
    3. dismissed_at set in state file (via `docglow cloud hide-hint`)
    4. Shown within FREQUENCY_WINDOW (24h) per machine
    5. Default: show and record timestamp

State is persisted in a small JSON file under `click.get_app_dir("docglow")`.
All I/O failures are swallowed — this feature must never break `generate`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

CLOUD_URL = "https://docglow.com/cloud"
SUPPRESS_ENV = "DOCGLOW_NO_CLOUD_HINT"
CI_ENV = "CI"
FREQUENCY_WINDOW = timedelta(hours=24)
STATE_FILENAME = "cloud_hint.json"
STATE_VERSION = 1

_TRUTHY = {"1", "true", "yes", "on"}


def _state_path() -> Path:
    """Return the path to the hint state file. Factored out for test monkeypatching."""
    return Path(click.get_app_dir("docglow")) / STATE_FILENAME


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


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


def _parse_iso8601(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _read_state(path: Path) -> datetime | None:
    """Return the last-shown timestamp, or None if missing/invalid."""
    return _parse_iso8601(_read_payload(path).get("last_shown_at"))


def _read_dismissed_at(path: Path) -> datetime | None:
    """Return the dismissed-at timestamp, or None if not dismissed."""
    return _parse_iso8601(_read_payload(path).get("dismissed_at"))


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist a state payload. Swallows all exceptions."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        # Best-effort: a failed write just means the hint may show again sooner.
        pass


def _write_state(path: Path, now: datetime) -> None:
    """Persist the last-shown timestamp while preserving any dismissed_at field."""
    existing = _read_payload(path)
    payload: dict[str, object] = {
        "version": STATE_VERSION,
        "last_shown_at": now.astimezone(timezone.utc).isoformat(),
    }
    dismissed_at = existing.get("dismissed_at")
    if isinstance(dismissed_at, str):
        payload["dismissed_at"] = dismissed_at
    _write_payload(path, payload)


def _write_dismissed_at(path: Path, when: datetime | None) -> None:
    """Set or clear the dismissed_at field while preserving any last_shown_at field.

    Passing `None` removes the dismissed_at field.
    """
    existing = _read_payload(path)
    payload: dict[str, object] = {"version": STATE_VERSION}
    last_shown_at = existing.get("last_shown_at")
    if isinstance(last_shown_at, str):
        payload["last_shown_at"] = last_shown_at
    if when is not None:
        payload["dismissed_at"] = when.astimezone(timezone.utc).isoformat()
    _write_payload(path, payload)


def set_dismissed(now: datetime | None = None) -> None:
    """Mark the Cloud hint as dismissed. Used by `docglow cloud hide-hint`."""
    _write_dismissed_at(_state_path(), now or datetime.now(timezone.utc))


def clear_dismissed() -> None:
    """Re-enable the Cloud hint. Used by `docglow cloud show-hint`."""
    _write_dismissed_at(_state_path(), None)


def should_show_hint(
    now: datetime,
    env: Mapping[str, str],
    state_path: Path,
) -> bool:
    """Apply the suppression precedence rules."""
    if _is_truthy(env.get(SUPPRESS_ENV)):
        return False
    if _is_truthy(env.get(CI_ENV)):
        return False
    if _read_dismissed_at(state_path) is not None:
        return False
    last_shown = _read_state(state_path)
    if last_shown is not None and (now - last_shown) < FREQUENCY_WINDOW:
        return False
    return True


def render_hint(version: str) -> str:
    """Return the Rich-markup hint string with UTM attribution and dismiss tip.

    UTM params are used (instead of custom keys) so PostHog and other
    analytics tools auto-capture them without extra configuration.
    """
    url = f"{CLOUD_URL}?utm_source=cli&utm_medium=cli&utm_campaign=generate&utm_content=v{version}"
    return (
        f"\n[dim]:bulb: Docglow Cloud: hosted docs + AI Q&A + Slack bot → {url}[/dim]"
        f"\n[dim]   (run `docglow cloud hide-hint` to dismiss)[/dim]"
    )


def maybe_show_hint(console: object, version: str) -> None:
    """Print the hint if suppression rules allow, then record state.

    Never raises. `console` is a rich.console.Console but typed as object to
    keep this module free of rich-typing coupling.
    """
    try:
        now = datetime.now(timezone.utc)
        path = _state_path()
        if not should_show_hint(now, os.environ, path):
            return
        console.print(render_hint(version))  # type: ignore[attr-defined]
        _write_state(path, now)
    except Exception:
        # Never let the hint break the generate command.
        pass
