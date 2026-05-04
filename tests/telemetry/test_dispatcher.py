"""Tests for docglow.telemetry.dispatcher."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from docglow.telemetry import state
from docglow.telemetry.config import (
    ENV_OPT_OUT,
    TelemetryConfig,
)
from docglow.telemetry.dispatcher import (
    is_active,
    project_shape_from_manifest_path,
    record_command,
)
from docglow.telemetry.payload import ProjectShape


def _enabled_config() -> TelemetryConfig:
    return TelemetryConfig(enabled=True, endpoint="http://localhost:1/telemetry")


def _disabled_config() -> TelemetryConfig:
    return TelemetryConfig(enabled=False, endpoint="http://localhost:1/telemetry")


# ---- is_active --------------------------------------------------------------


def test_is_active_when_config_enabled_and_no_consent_required() -> None:
    assert is_active(_enabled_config(), consent="unset", env={}) is True


def test_is_active_when_consent_yes_even_if_config_disabled() -> None:
    assert is_active(_disabled_config(), consent="yes", env={}) is True


def test_is_active_false_when_disabled_and_consent_unset() -> None:
    assert is_active(_disabled_config(), consent="unset", env={}) is False


def test_is_active_false_when_consent_no() -> None:
    assert is_active(_disabled_config(), consent="no", env={}) is False


def test_no_telemetry_env_overrides_consent_yes() -> None:
    assert is_active(_disabled_config(), consent="yes", env={ENV_OPT_OUT: "1"}) is False


def test_no_telemetry_env_overrides_config_enabled() -> None:
    # Config could still report enabled=True if it was constructed with
    # injected env that didn't include opt-out; the dispatcher re-checks.
    assert is_active(_enabled_config(), consent="yes", env={ENV_OPT_OUT: "1"}) is False


# ---- record_command ---------------------------------------------------------


def test_record_command_returns_none_when_inactive(tmp_path: Path) -> None:
    state_path = tmp_path / "telemetry.json"
    payload = record_command(
        _disabled_config(),
        command="generate",
        result="success",
        duration_ms=10,
        consent="no",
        state_path=state_path,
        send=False,
    )
    assert payload is None


def test_record_command_builds_payload_when_active(tmp_path: Path) -> None:
    state_path = tmp_path / "telemetry.json"
    payload = record_command(
        _enabled_config(),
        command="generate",
        result="success",
        duration_ms=42,
        project_shape=ProjectShape(models=3, adapter_type="duckdb"),
        consent="unset",
        state_path=state_path,
        send=False,
    )
    assert payload is not None
    assert payload["command"] == "generate"
    assert payload["result"] == "success"
    assert payload["duration_ms"] == 42
    assert payload["adapter_type"] == "duckdb"
    assert payload["project_shape"]["models"] == 3
    # Instance ID is generated and persisted
    assert isinstance(payload["instance_id"], str)
    assert state_path.exists()


def test_record_command_uses_consent_from_state_file_when_not_passed(tmp_path: Path) -> None:
    state_path = tmp_path / "telemetry.json"
    state.set_consent("yes", state_path)
    payload = record_command(
        _disabled_config(),
        command="health",
        result="success",
        duration_ms=10,
        state_path=state_path,
        send=False,
    )
    assert payload is not None  # consent=yes from state file activates dispatch


def test_record_command_does_not_send_when_send_false(tmp_path: Path) -> None:
    state_path = tmp_path / "telemetry.json"
    with patch("docglow.telemetry.dispatcher.client.send") as mock_send:
        record_command(
            _enabled_config(),
            command="generate",
            result="success",
            duration_ms=10,
            consent="yes",
            state_path=state_path,
            send=False,
        )
    mock_send.assert_not_called()


def test_record_command_sends_via_client_when_active(tmp_path: Path) -> None:
    state_path = tmp_path / "telemetry.json"
    with patch("docglow.telemetry.dispatcher.client.send") as mock_send:
        record_command(
            _enabled_config(),
            command="generate",
            result="success",
            duration_ms=10,
            consent="yes",
            state_path=state_path,
        )
    mock_send.assert_called_once()
    args, _kwargs = mock_send.call_args
    payload, endpoint = args
    assert payload["command"] == "generate"
    assert endpoint == "http://localhost:1/telemetry"


def test_record_command_swallows_internal_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_path = tmp_path / "telemetry.json"

    def boom(*_args, **_kwargs) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("docglow.telemetry.dispatcher.build_event", boom)
    # Should not raise even though build_event explodes
    payload = record_command(
        _enabled_config(),
        command="generate",
        result="success",
        duration_ms=10,
        consent="yes",
        state_path=state_path,
    )
    assert payload is None


# ---- project_shape_from_manifest_path --------------------------------------


def test_manifest_path_peek_missing_file_returns_zero(tmp_path: Path) -> None:
    shape = project_shape_from_manifest_path(tmp_path)
    assert shape == ProjectShape()


def test_manifest_path_peek_corrupt_json_returns_zero(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
    shape = project_shape_from_manifest_path(tmp_path)
    assert shape == ProjectShape()


def test_manifest_path_peek_counts_resource_types(tmp_path: Path) -> None:
    manifest_data = {
        "metadata": {"adapter_type": "Snowflake"},
        "nodes": {
            "model.x.a": {"resource_type": "model"},
            "model.x.b": {"resource_type": "model"},
            "test.x.t1": {"resource_type": "test"},
            "seed.x.s1": {"resource_type": "seed"},
            "snapshot.x.sn1": {"resource_type": "snapshot"},  # not counted
        },
        "sources": {"source.x.a": {}, "source.x.b": {}},
        "macros": {"macro.x.m1": {}},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    shape = project_shape_from_manifest_path(tmp_path)
    assert shape.models == 2
    assert shape.tests == 1
    assert shape.seeds == 1
    assert shape.sources == 2
    assert shape.macros == 1
    assert shape.adapter_type == "snowflake"


def test_manifest_path_peek_missing_metadata_returns_none_adapter(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        json.dumps({"nodes": {}, "sources": {}, "macros": {}}), encoding="utf-8"
    )
    shape = project_shape_from_manifest_path(tmp_path)
    assert shape.adapter_type is None
