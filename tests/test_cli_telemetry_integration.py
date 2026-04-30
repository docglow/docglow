"""Integration tests verifying telemetry dispatch from CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docglow import cloud_hint
from docglow.cli import cli
from docglow.telemetry.config import TelemetryConfig


def _mock_config(telemetry_enabled: bool = False) -> MagicMock:
    config = MagicMock()
    config.ai.enabled = False
    config.title = "docglow"
    config.slim = False
    config.column_lineage = True
    config.telemetry = TelemetryConfig(
        enabled=telemetry_enabled, endpoint="http://localhost:1/telemetry"
    )
    return config


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "cloud_hint.json"
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state)
    monkeypatch.setenv("DOCGLOW_NO_CLOUD_HINT", "1")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("DOCGLOW_TELEMETRY", raising=False)
    monkeypatch.delenv("DOCGLOW_NO_TELEMETRY", raising=False)


def test_generate_records_success_event_when_telemetry_enabled(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config(telemetry_enabled=True)),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 85.0),
        ),
        patch("docglow.telemetry.dispatcher.record_command") as mock_record,
    ):
        result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    mock_record.assert_called_once()
    kwargs = mock_record.call_args.kwargs
    assert kwargs["command"] == "generate"
    assert kwargs["result"] == "success"
    assert "duration_ms" in kwargs
    assert isinstance(kwargs["duration_ms"], int)


def test_generate_records_error_event_on_failure(tmp_path: Path) -> None:
    from docglow.artifacts.loader import ArtifactLoadError

    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config(telemetry_enabled=True)),
        patch(
            "docglow.generator.site.generate_site",
            side_effect=ArtifactLoadError("manifest missing"),
        ),
        patch("docglow.telemetry.dispatcher.record_command") as mock_record,
    ):
        result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

    assert result.exit_code == 1
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["result"] == "error"


def test_generate_records_error_when_fail_under_trips(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config(telemetry_enabled=True)),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 40.0),
        ),
        patch("docglow.telemetry.dispatcher.record_command") as mock_record,
    ):
        result = runner.invoke(
            cli, ["generate", "--project-dir", str(tmp_path), "--fail-under", "70"]
        )

    assert result.exit_code == 1
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["result"] == "error"


def test_generate_dispatcher_still_called_when_telemetry_disabled(tmp_path: Path) -> None:
    """When disabled, record_command is still invoked but is internally a no-op.

    The gate logic lives inside record_command, not at the call site -- this
    keeps the command-level wiring trivial and centralises the gate.
    """
    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config(telemetry_enabled=False)),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 85.0),
        ),
        patch("docglow.telemetry.dispatcher.record_command") as mock_record,
    ):
        result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

    assert result.exit_code == 0
    mock_record.assert_called_once()


def test_generate_features_used_reflects_active_flags(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config(telemetry_enabled=True)),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 85.0),
        ),
        patch("docglow.telemetry.dispatcher.record_command") as mock_record,
    ):
        runner.invoke(
            cli,
            [
                "generate",
                "--project-dir",
                str(tmp_path),
                "--static",
                "--slim",
                "--skip-column-lineage",
            ],
        )

    features = mock_record.call_args.kwargs["features_used"]
    assert "column_lineage" not in features
    assert "static" in features
    assert "slim" in features
