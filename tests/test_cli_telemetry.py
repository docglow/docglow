"""Tests for docglow telemetry status|enable|disable subcommands and the
first-run consent prompt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from docglow.cli import cli
from docglow.commands.telemetry import maybe_prompt_for_consent
from docglow.telemetry import state


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state_path = tmp_path / "telemetry.json"
    monkeypatch.setattr(state, "_state_path", lambda: state_path)
    monkeypatch.delenv("DOCGLOW_TELEMETRY", raising=False)
    monkeypatch.delenv("DOCGLOW_NO_TELEMETRY", raising=False)
    monkeypatch.delenv("DOCGLOW_TELEMETRY_ENDPOINT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    return state_path


# ---- subcommands -----------------------------------------------------------


def test_telemetry_status_default_is_inactive(isolated_state: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Active: no" in result.output
    assert "Recorded consent: unset" in result.output


def test_telemetry_enable_records_consent(isolated_state: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["telemetry", "enable"])
    assert result.exit_code == 0
    assert state.get_consent(isolated_state) == "yes"

    result = runner.invoke(cli, ["telemetry", "status"])
    assert "Active: yes" in result.output
    assert "Recorded consent: yes" in result.output


def test_telemetry_disable_records_consent(isolated_state: Path) -> None:
    runner = CliRunner()
    state.set_consent("yes", isolated_state)

    result = runner.invoke(cli, ["telemetry", "disable"])
    assert result.exit_code == 0
    assert state.get_consent(isolated_state) == "no"

    result = runner.invoke(cli, ["telemetry", "status"])
    assert "Active: no" in result.output
    assert "Recorded consent: no" in result.output


def test_telemetry_status_reflects_no_telemetry_env_override(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state.set_consent("yes", isolated_state)
    monkeypatch.setenv("DOCGLOW_NO_TELEMETRY", "1")

    runner = CliRunner()
    result = runner.invoke(cli, ["telemetry", "status"])
    assert "Active: no" in result.output


def test_telemetry_status_shows_endpoint_override(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCGLOW_TELEMETRY_ENDPOINT", "https://override.test/")

    runner = CliRunner()
    result = runner.invoke(cli, ["telemetry", "status"])
    assert "https://override.test/" in result.output


def test_telemetry_status_shows_instance_id(isolated_state: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["telemetry", "status"])
    assert result.exit_code == 0
    # Instance ID line is present
    assert "Instance ID:" in result.output


# ---- consent prompt --------------------------------------------------------


def test_prompt_skipped_when_ci_env_set(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CI", "true")
    consent = maybe_prompt_for_consent()
    # Consent was recorded as "no" so we never re-prompt
    assert consent == "no"
    assert state.get_consent(isolated_state) == "no"


def test_prompt_skipped_when_stdin_not_tty(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # In test contexts stdin is typically not a TTY, so the prompt should
    # be suppressed and consent recorded as "no".
    consent = maybe_prompt_for_consent()
    assert consent == "no"
    assert state.get_consent(isolated_state) == "no"


def test_prompt_skipped_when_no_telemetry_env_set(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCGLOW_NO_TELEMETRY", "1")
    consent = maybe_prompt_for_consent()
    assert consent == "no"


def test_prompt_not_shown_again_after_decision(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state.set_consent("yes", isolated_state)
    # Even with a TTY, an existing consent value short-circuits the prompt.
    consent = maybe_prompt_for_consent()
    assert consent == "yes"


def test_prompt_does_not_overwrite_explicit_no(
    isolated_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state.set_consent("no", isolated_state)
    consent = maybe_prompt_for_consent()
    assert consent == "no"


# ---- generate runs the prompt only when consent is unset -------------------


def test_generate_records_implicit_no_consent_when_non_interactive(
    isolated_state: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running generate non-interactively should record consent=no automatically."""
    from unittest.mock import MagicMock, patch

    from docglow.telemetry.config import TelemetryConfig

    monkeypatch.setenv("DOCGLOW_NO_CLOUD_HINT", "1")

    mock_config = MagicMock()
    mock_config.ai.enabled = False
    mock_config.title = "docglow"
    mock_config.slim = False
    mock_config.column_lineage = True
    mock_config.telemetry = TelemetryConfig(enabled=False, endpoint="http://localhost:1/telemetry")

    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=mock_config),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 85.0),
        ),
    ):
        result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

    assert result.exit_code == 0
    # The prompt was suppressed in the non-TTY runner context, so consent
    # should have flipped from "unset" to "no".
    assert state.get_consent(isolated_state) == "no"
