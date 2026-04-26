"""Unit tests for docglow.cloud_hint suppression and state handling."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docglow import cloud_hint
from docglow.cloud_hint import (
    FREQUENCY_WINDOW,
    STATE_VERSION,
    _read_dismissed_at,
    _read_state,
    _write_dismissed_at,
    _write_state,
    clear_dismissed,
    maybe_show_hint,
    render_hint,
    set_dismissed,
    should_show_hint,
)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "docglow" / "cloud_hint.json"


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


def test_should_show_hint_first_run(state_path: Path, fixed_now: datetime) -> None:
    assert should_show_hint(fixed_now, {}, state_path) is True


def test_should_show_hint_suppressed_by_env_var(state_path: Path, fixed_now: datetime) -> None:
    assert should_show_hint(fixed_now, {"DOCGLOW_NO_CLOUD_HINT": "1"}, state_path) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On"])
def test_should_show_hint_env_var_truthy_variants(
    state_path: Path, fixed_now: datetime, value: str
) -> None:
    assert should_show_hint(fixed_now, {"DOCGLOW_NO_CLOUD_HINT": value}, state_path) is False


@pytest.mark.parametrize("value", ["0", "", "false", "no"])
def test_should_show_hint_env_var_falsy_variants(
    state_path: Path, fixed_now: datetime, value: str
) -> None:
    assert should_show_hint(fixed_now, {"DOCGLOW_NO_CLOUD_HINT": value}, state_path) is True


def test_should_show_hint_suppressed_in_ci(state_path: Path, fixed_now: datetime) -> None:
    assert should_show_hint(fixed_now, {"CI": "true"}, state_path) is False


def test_should_show_hint_within_window(state_path: Path, fixed_now: datetime) -> None:
    recent = fixed_now - timedelta(hours=1)
    _write_state(state_path, recent)
    assert should_show_hint(fixed_now, {}, state_path) is False


def test_should_show_hint_outside_window(state_path: Path, fixed_now: datetime) -> None:
    stale = fixed_now - timedelta(hours=25)
    _write_state(state_path, stale)
    assert should_show_hint(fixed_now, {}, state_path) is True


def test_should_show_hint_corrupt_state_file(state_path: Path, fixed_now: datetime) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not json", encoding="utf-8")
    assert should_show_hint(fixed_now, {}, state_path) is True


def test_should_show_hint_missing_timestamp_field(state_path: Path, fixed_now: datetime) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"version": STATE_VERSION}), encoding="utf-8")
    assert should_show_hint(fixed_now, {}, state_path) is True


def test_should_show_hint_unknown_state_version(state_path: Path, fixed_now: datetime) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"version": 99, "last_shown_at": fixed_now.isoformat()}),
        encoding="utf-8",
    )
    assert should_show_hint(fixed_now, {}, state_path) is True


def test_read_state_missing_file(state_path: Path) -> None:
    assert _read_state(state_path) is None


def test_write_state_creates_parent_dir(state_path: Path, fixed_now: datetime) -> None:
    assert not state_path.parent.exists()
    _write_state(state_path, fixed_now)
    assert state_path.exists()
    loaded = _read_state(state_path)
    assert loaded is not None
    assert loaded == fixed_now


def test_write_state_atomic_overwrite(state_path: Path, fixed_now: datetime) -> None:
    _write_state(state_path, fixed_now)
    later = fixed_now + timedelta(hours=5)
    _write_state(state_path, later)
    loaded = _read_state(state_path)
    assert loaded == later


def test_write_state_swallows_errors(
    state_path: Path, fixed_now: datetime, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    # Must not raise.
    _write_state(state_path, fixed_now)


def test_render_hint_contains_utm_attribution() -> None:
    output = render_hint("0.7.3")
    assert "docglow.com/cloud?" in output
    assert "utm_source=cli" in output
    assert "utm_medium=cli" in output
    assert "utm_campaign=generate" in output
    assert "utm_content=v0.7.3" in output
    assert ":bulb:" in output


def test_render_hint_contains_dismiss_tip() -> None:
    output = render_hint("0.7.3")
    assert "hide-hint" in output
    assert "dismiss" in output


def test_maybe_show_hint_env_var_wins_over_everything(
    state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    monkeypatch.setenv("DOCGLOW_NO_CLOUD_HINT", "1")
    monkeypatch.delenv("CI", raising=False)
    console = MagicMock()
    maybe_show_hint(console, "0.7.3")
    console.print.assert_not_called()
    assert not state_path.exists()


def test_maybe_show_hint_ci_suppression(state_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    monkeypatch.delenv("DOCGLOW_NO_CLOUD_HINT", raising=False)
    monkeypatch.setenv("CI", "true")
    console = MagicMock()
    maybe_show_hint(console, "0.7.3")
    console.print.assert_not_called()
    assert not state_path.exists()


def test_maybe_show_hint_writes_state_on_show(
    state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    monkeypatch.delenv("DOCGLOW_NO_CLOUD_HINT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    console = MagicMock()
    maybe_show_hint(console, "0.7.3")
    console.print.assert_called_once()
    assert state_path.exists()


def test_maybe_show_hint_never_raises(state_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Path:
        raise RuntimeError("config dir unreadable")

    monkeypatch.setattr(cloud_hint, "_state_path", boom)
    console = MagicMock()
    # Must not raise even though _state_path blows up.
    maybe_show_hint(console, "0.7.3")


def test_maybe_show_hint_respects_frequency_cap(
    state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    monkeypatch.delenv("DOCGLOW_NO_CLOUD_HINT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    _write_state(state_path, datetime.now(timezone.utc) - timedelta(hours=1))
    console = MagicMock()
    maybe_show_hint(console, "0.7.3")
    console.print.assert_not_called()


def test_frequency_window_is_24h() -> None:
    assert FREQUENCY_WINDOW == timedelta(hours=24)


# --- dismiss-flag tests ---


def test_read_dismissed_at_missing_file(state_path: Path) -> None:
    assert _read_dismissed_at(state_path) is None


def test_read_dismissed_at_when_field_present(state_path: Path, fixed_now: datetime) -> None:
    _write_dismissed_at(state_path, fixed_now)
    loaded = _read_dismissed_at(state_path)
    assert loaded is not None
    assert loaded == fixed_now


def test_read_dismissed_at_returns_none_for_corrupt_payload(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not json", encoding="utf-8")
    assert _read_dismissed_at(state_path) is None


def test_read_dismissed_at_returns_none_for_unknown_version(
    state_path: Path, fixed_now: datetime
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"version": 99, "dismissed_at": fixed_now.isoformat()}),
        encoding="utf-8",
    )
    assert _read_dismissed_at(state_path) is None


def test_write_dismissed_at_preserves_last_shown_at(state_path: Path, fixed_now: datetime) -> None:
    _write_state(state_path, fixed_now)
    later = fixed_now + timedelta(hours=2)
    _write_dismissed_at(state_path, later)
    assert _read_state(state_path) == fixed_now
    assert _read_dismissed_at(state_path) == later


def test_write_dismissed_at_none_clears_field(state_path: Path, fixed_now: datetime) -> None:
    _write_state(state_path, fixed_now)
    _write_dismissed_at(state_path, fixed_now + timedelta(hours=1))
    assert _read_dismissed_at(state_path) is not None
    _write_dismissed_at(state_path, None)
    assert _read_dismissed_at(state_path) is None
    assert _read_state(state_path) == fixed_now


def test_write_dismissed_at_creates_parent_dir(state_path: Path, fixed_now: datetime) -> None:
    assert not state_path.parent.exists()
    _write_dismissed_at(state_path, fixed_now)
    assert state_path.exists()
    assert _read_dismissed_at(state_path) == fixed_now


def test_write_state_preserves_dismissed_at(state_path: Path, fixed_now: datetime) -> None:
    _write_dismissed_at(state_path, fixed_now)
    later = fixed_now + timedelta(hours=3)
    _write_state(state_path, later)
    assert _read_state(state_path) == later
    assert _read_dismissed_at(state_path) == fixed_now


def test_should_show_hint_suppressed_when_dismissed(state_path: Path, fixed_now: datetime) -> None:
    _write_dismissed_at(state_path, fixed_now - timedelta(days=30))
    assert should_show_hint(fixed_now, {}, state_path) is False


def test_should_show_hint_dismissed_overrides_window_age(
    state_path: Path, fixed_now: datetime
) -> None:
    """Dismissal suppresses regardless of how long ago it occurred."""
    _write_dismissed_at(state_path, fixed_now - timedelta(days=365))
    assert should_show_hint(fixed_now, {}, state_path) is False


def test_should_show_hint_after_dismiss_cleared(state_path: Path, fixed_now: datetime) -> None:
    _write_dismissed_at(state_path, fixed_now - timedelta(hours=1))
    _write_dismissed_at(state_path, None)
    assert should_show_hint(fixed_now, {}, state_path) is True


def test_set_dismissed_uses_state_path(state_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    set_dismissed()
    assert _read_dismissed_at(state_path) is not None


def test_clear_dismissed_uses_state_path(
    state_path: Path, monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    _write_dismissed_at(state_path, fixed_now)
    clear_dismissed()
    assert _read_dismissed_at(state_path) is None


def test_clear_dismissed_idempotent_when_not_dismissed(
    state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    # No prior state — clear should not raise and should leave a clean state.
    clear_dismissed()
    assert _read_dismissed_at(state_path) is None


def test_maybe_show_hint_suppressed_when_dismissed(
    state_path: Path, monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
) -> None:
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state_path)
    monkeypatch.delenv("DOCGLOW_NO_CLOUD_HINT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    _write_dismissed_at(state_path, fixed_now)
    console = MagicMock()
    maybe_show_hint(console, "0.7.3")
    console.print.assert_not_called()
