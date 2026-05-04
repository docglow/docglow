"""Tests for docglow.telemetry.config."""

from __future__ import annotations

import pytest

from docglow.telemetry.config import (
    DEFAULT_ENDPOINT,
    ENV_ENDPOINT_OVERRIDE,
    ENV_OPT_IN,
    ENV_OPT_OUT,
    TelemetryConfig,
    resolve_telemetry_config,
)


def test_default_disabled_with_no_yml_or_env() -> None:
    config = resolve_telemetry_config(None, env={})
    assert config == TelemetryConfig(enabled=False, endpoint=DEFAULT_ENDPOINT)


def test_yml_enabled_true_no_env() -> None:
    config = resolve_telemetry_config({"enabled": True}, env={})
    assert config.enabled is True


def test_env_opt_in_overrides_yml_disabled() -> None:
    config = resolve_telemetry_config({"enabled": False}, env={ENV_OPT_IN: "1"})
    assert config.enabled is True


def test_env_opt_in_zero_overrides_yml_enabled() -> None:
    config = resolve_telemetry_config({"enabled": True}, env={ENV_OPT_IN: "0"})
    assert config.enabled is False


def test_no_telemetry_beats_opt_in() -> None:
    config = resolve_telemetry_config({"enabled": True}, env={ENV_OPT_IN: "1", ENV_OPT_OUT: "1"})
    assert config.enabled is False


def test_no_telemetry_beats_yml_enabled() -> None:
    config = resolve_telemetry_config({"enabled": True}, env={ENV_OPT_OUT: "1"})
    assert config.enabled is False


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on", "  YES  "])
def test_truthy_env_values_recognised(truthy: str) -> None:
    config = resolve_telemetry_config(None, env={ENV_OPT_IN: truthy})
    assert config.enabled is True


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off"])
def test_falsy_env_values_recognised(falsy: str) -> None:
    config = resolve_telemetry_config({"enabled": True}, env={ENV_OPT_IN: falsy})
    assert config.enabled is False


def test_unknown_env_value_falls_through_to_yml() -> None:
    config = resolve_telemetry_config({"enabled": True}, env={ENV_OPT_IN: "maybe"})
    assert config.enabled is True


def test_endpoint_default() -> None:
    config = resolve_telemetry_config(None, env={})
    assert config.endpoint == DEFAULT_ENDPOINT


def test_endpoint_yml_override() -> None:
    config = resolve_telemetry_config({"endpoint": "https://example.test/e"}, env={})
    assert config.endpoint == "https://example.test/e"


def test_endpoint_env_overrides_yml() -> None:
    config = resolve_telemetry_config(
        {"endpoint": "https://yml.test/e"},
        env={ENV_ENDPOINT_OVERRIDE: "https://env.test/e"},
    )
    assert config.endpoint == "https://env.test/e"


def test_yml_missing_enabled_treated_as_disabled() -> None:
    config = resolve_telemetry_config({}, env={})
    assert config.enabled is False


def test_yml_non_dict_treated_as_missing() -> None:
    # A user who writes ``telemetry: true`` (rather than ``telemetry: {enabled: true}``)
    # should get sane behaviour, not a crash.
    config = resolve_telemetry_config("not-a-dict", env={ENV_OPT_IN: "1"})  # type: ignore[arg-type]
    assert config.enabled is True


def test_default_uses_real_environ_when_env_not_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_OPT_IN, "1")
    config = resolve_telemetry_config(None)
    assert config.enabled is True
