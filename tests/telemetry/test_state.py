"""Tests for docglow.telemetry.state."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from docglow.telemetry import state


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "telemetry.json"


def test_get_instance_id_generates_and_persists(state_path: Path) -> None:
    assert not state_path.exists()
    instance_id = state.get_instance_id(state_path)
    uuid.UUID(instance_id)  # raises if not a valid UUID
    assert state_path.exists()
    payload = json.loads(state_path.read_text())
    assert payload["instance_id"] == instance_id
    assert payload["version"] == state.STATE_VERSION
    assert payload["consent"] == "unset"


def test_get_instance_id_is_stable_across_calls(state_path: Path) -> None:
    first = state.get_instance_id(state_path)
    second = state.get_instance_id(state_path)
    third = state.get_instance_id(state_path)
    assert first == second == third


def test_get_instance_id_recovers_from_corrupt_json(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not valid json", encoding="utf-8")
    instance_id = state.get_instance_id(state_path)
    uuid.UUID(instance_id)
    # File should now contain a valid payload
    payload = json.loads(state_path.read_text())
    assert payload["instance_id"] == instance_id


def test_get_instance_id_recovers_from_unknown_version(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"version": 999, "instance_id": "leftover"}), encoding="utf-8")
    instance_id = state.get_instance_id(state_path)
    uuid.UUID(instance_id)
    assert instance_id != "leftover"


def test_get_instance_id_recovers_from_invalid_uuid(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"version": state.STATE_VERSION, "instance_id": "not-a-uuid"}),
        encoding="utf-8",
    )
    instance_id = state.get_instance_id(state_path)
    uuid.UUID(instance_id)
    assert instance_id != "not-a-uuid"


def test_get_instance_id_when_directory_unwritable_does_not_raise(
    state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force write failures by pointing to an unwritable path
    bad_path = state_path / "telemetry.json"  # parent is a file that doesn't exist
    state_path.write_text("blocker")  # makes state_path a file, so bad_path's parent IS a file

    # Should not raise even though writes will fail
    instance_id = state.get_instance_id(bad_path)
    uuid.UUID(instance_id)


def test_get_consent_default_is_unset(state_path: Path) -> None:
    assert state.get_consent(state_path) == "unset"


def test_set_consent_yes(state_path: Path) -> None:
    state.set_consent("yes", state_path)
    assert state.get_consent(state_path) == "yes"
    payload = json.loads(state_path.read_text())
    assert "consent_recorded_at" in payload
    uuid.UUID(payload["instance_id"])


def test_set_consent_no(state_path: Path) -> None:
    state.set_consent("no", state_path)
    assert state.get_consent(state_path) == "no"
    payload = json.loads(state_path.read_text())
    assert "consent_recorded_at" in payload


def test_set_consent_preserves_instance_id(state_path: Path) -> None:
    instance_id = state.get_instance_id(state_path)
    state.set_consent("yes", state_path)
    state.set_consent("no", state_path)
    payload = json.loads(state_path.read_text())
    assert payload["instance_id"] == instance_id


def test_set_consent_generates_instance_id_when_missing(state_path: Path) -> None:
    assert not state_path.exists()
    state.set_consent("yes", state_path)
    payload = json.loads(state_path.read_text())
    uuid.UUID(payload["instance_id"])


def test_set_consent_unset_clears_recorded_at(state_path: Path) -> None:
    state.set_consent("yes", state_path)
    state.set_consent("unset", state_path)
    payload = json.loads(state_path.read_text())
    assert payload["consent"] == "unset"
    assert "consent_recorded_at" not in payload


def test_set_consent_rejects_invalid_value(state_path: Path) -> None:
    with pytest.raises(ValueError):
        state.set_consent("maybe", state_path)  # type: ignore[arg-type]


def test_get_consent_normalizes_unknown_value(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "version": state.STATE_VERSION,
                "instance_id": str(uuid.uuid4()),
                "consent": "maybe",
            }
        ),
        encoding="utf-8",
    )
    assert state.get_consent(state_path) == "unset"


def test_default_path_uses_click_app_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "docglow.telemetry.state.click.get_app_dir",
        lambda _name: str(tmp_path / "appdir"),
    )
    p = state._state_path()
    assert p == tmp_path / "appdir" / state.STATE_FILENAME
