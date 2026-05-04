"""Tests for docglow.telemetry.payload."""

from __future__ import annotations

import json
import sys

import pytest

import docglow as _docglow
from docglow.telemetry.payload import (
    SCHEMA_VERSION,
    ProjectShape,
    build_event,
)

EXPECTED_KEYS = {
    "schema_version",
    "instance_id",
    "command",
    "result",
    "duration_ms",
    "docglow_version",
    "python_version",
    "platform",
    "adapter_type",
    "project_shape",
    "features_used",
}


def _base_event(**overrides):
    kwargs = dict(
        instance_id="00000000-0000-0000-0000-000000000001",
        command="generate",
        result="success",
        duration_ms=1234,
        project_shape=ProjectShape(
            models=10, sources=2, seeds=1, tests=5, macros=0, adapter_type="duckdb"
        ),
        features_used=("column_lineage",),
    )
    kwargs.update(overrides)
    return build_event(**kwargs)


def test_payload_keys_are_exactly_the_documented_set() -> None:
    event = _base_event()
    assert set(event.keys()) == EXPECTED_KEYS


def test_payload_is_json_serialisable() -> None:
    event = _base_event()
    # Must round-trip cleanly; if a field is non-serialisable we want to know.
    json.dumps(event)


def test_schema_version_is_v1() -> None:
    event = _base_event()
    assert event["schema_version"] == SCHEMA_VERSION == 1


def test_carries_through_known_fields() -> None:
    event = _base_event()
    assert event["instance_id"] == "00000000-0000-0000-0000-000000000001"
    assert event["command"] == "generate"
    assert event["result"] == "success"
    assert event["duration_ms"] == 1234
    assert event["docglow_version"] == _docglow.__version__
    assert event["adapter_type"] == "duckdb"
    assert event["features_used"] == ["column_lineage"]


def test_python_version_is_dotted_triple() -> None:
    event = _base_event()
    parts = event["python_version"].split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
    assert parts[0] == str(sys.version_info.major)


def test_platform_is_one_of_known_values() -> None:
    event = _base_event()
    assert event["platform"] in {"linux", "darwin", "windows", "other"}


def test_empty_project_shape_yields_zero_counts() -> None:
    event = build_event(
        instance_id="x",
        command="health",
        result="success",
        duration_ms=0,
        project_shape=ProjectShape(),
    )
    assert event["project_shape"] == {
        "models": 0,
        "sources": 0,
        "seeds": 0,
        "tests": 0,
        "macros": 0,
    }
    assert event["adapter_type"] is None


def test_none_project_shape_treated_as_empty() -> None:
    event = build_event(
        instance_id="x",
        command="serve",
        result="success",
        duration_ms=0,
        project_shape=None,
    )
    assert event["project_shape"]["models"] == 0
    assert event["adapter_type"] is None


def test_adapter_type_null_is_present_not_omitted() -> None:
    event = build_event(
        instance_id="x",
        command="generate",
        result="success",
        duration_ms=0,
        project_shape=ProjectShape(),
    )
    assert "adapter_type" in event
    assert event["adapter_type"] is None


def test_features_used_empty_list_present_not_omitted() -> None:
    event = build_event(
        instance_id="x",
        command="generate",
        result="success",
        duration_ms=0,
        project_shape=None,
    )
    assert "features_used" in event
    assert event["features_used"] == []


def test_duration_ms_coerced_to_int() -> None:
    event = build_event(
        instance_id="x",
        command="generate",
        result="success",
        duration_ms=42.7,  # type: ignore[arg-type]
        project_shape=None,
    )
    assert event["duration_ms"] == 42
    assert isinstance(event["duration_ms"], int)


@pytest.mark.parametrize("command", ["generate", "health", "serve"])
def test_all_documented_commands_accepted(command: str) -> None:
    event = build_event(
        instance_id="x",
        command=command,  # type: ignore[arg-type]
        result="success",
        duration_ms=0,
        project_shape=None,
    )
    assert event["command"] == command


@pytest.mark.parametrize("result", ["success", "error"])
def test_all_documented_results_accepted(result: str) -> None:
    event = build_event(
        instance_id="x",
        command="generate",
        result=result,  # type: ignore[arg-type]
        duration_ms=0,
        project_shape=None,
    )
    assert event["result"] == result


def test_snapshot_pins_v1_shape() -> None:
    """Snapshot test -- a deliberate change to the payload shape must update this.

    This is the load-bearing test against accidental schema drift. If a new
    field is added without updating docs/telemetry.md, this test will fail
    and force a conscious decision about what's being shipped.
    """
    event = build_event(
        instance_id="00000000-0000-0000-0000-000000000001",
        command="generate",
        result="success",
        duration_ms=4218,
        project_shape=ProjectShape(
            models=142, sources=31, seeds=4, tests=213, macros=8, adapter_type="snowflake"
        ),
        features_used=("column_lineage", "health_score"),
    )
    # Pin the keys (values like docglow_version, python_version, platform vary).
    assert set(event.keys()) == EXPECTED_KEYS
    assert set(event["project_shape"].keys()) == {"models", "sources", "seeds", "tests", "macros"}
