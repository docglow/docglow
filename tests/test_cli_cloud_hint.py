"""Integration tests for the Docglow Cloud hint in `docglow generate`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docglow import cloud_hint
from docglow.cli import cli


def _mock_config() -> MagicMock:
    config = MagicMock()
    config.ai.enabled = False
    config.title = "docglow"
    config.slim = False
    config.column_lineage = True
    return config


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the hint state file to tmp so tests don't pollute ~/.config/docglow."""
    state = tmp_path / "cloud_hint.json"
    monkeypatch.setattr(cloud_hint, "_state_path", lambda: state)
    monkeypatch.delenv("DOCGLOW_NO_CLOUD_HINT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    return state


def _invoke_generate(tmp_path: Path) -> object:
    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config()),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 85.0),
        ),
    ):
        return runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])


def test_generate_prints_cloud_hint_on_success(tmp_path: Path) -> None:
    result = _invoke_generate(tmp_path)
    assert result.exit_code == 0
    assert "Docglow Cloud" in result.output
    assert "utm_source=cli" in result.output


def test_generate_suppresses_hint_with_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCGLOW_NO_CLOUD_HINT", "1")
    result = _invoke_generate(tmp_path)
    assert result.exit_code == 0
    assert "Docglow Cloud" not in result.output


def test_generate_suppresses_hint_in_ci(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    result = _invoke_generate(tmp_path)
    assert result.exit_code == 0
    assert "Docglow Cloud" not in result.output


def test_generate_hint_not_shown_when_fail_under_trips(tmp_path: Path) -> None:
    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config()),
        patch(
            "docglow.generator.site.generate_site",
            return_value=(tmp_path / "output", 40.0),
        ),
    ):
        result = runner.invoke(
            cli,
            ["generate", "--project-dir", str(tmp_path), "--fail-under", "70"],
        )

    assert result.exit_code == 1
    assert "Docglow Cloud" not in result.output


def test_generate_hint_not_shown_on_artifact_error(
    tmp_path: Path,
) -> None:
    from docglow.artifacts.loader import ArtifactLoadError

    runner = CliRunner()
    with (
        patch("docglow.config.load_config", return_value=_mock_config()),
        patch(
            "docglow.generator.site.generate_site",
            side_effect=ArtifactLoadError("missing manifest"),
        ),
    ):
        result = runner.invoke(cli, ["generate", "--project-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "Docglow Cloud" not in result.output


# --- `docglow cloud hide-hint` / `show-hint` subcommands ---


def test_cloud_help_lists_hint_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["cloud", "--help"])
    assert result.exit_code == 0
    assert "hide-hint" in result.output
    assert "show-hint" in result.output


def test_cloud_hide_hint_writes_dismissed_state(isolated_state: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["cloud", "hide-hint"])
    assert result.exit_code == 0
    assert "dismissed" in result.output.lower()
    assert cloud_hint._read_dismissed_at(isolated_state) is not None


def test_cloud_show_hint_clears_dismissed_state(isolated_state: Path) -> None:
    runner = CliRunner()
    runner.invoke(cli, ["cloud", "hide-hint"])
    assert cloud_hint._read_dismissed_at(isolated_state) is not None
    result = runner.invoke(cli, ["cloud", "show-hint"])
    assert result.exit_code == 0
    assert "re-enabled" in result.output.lower()
    assert cloud_hint._read_dismissed_at(isolated_state) is None


def test_cloud_show_hint_idempotent_when_not_dismissed(isolated_state: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["cloud", "show-hint"])
    assert result.exit_code == 0
    assert cloud_hint._read_dismissed_at(isolated_state) is None


def test_cloud_hide_hint_idempotent_when_called_twice(isolated_state: Path) -> None:
    runner = CliRunner()
    result1 = runner.invoke(cli, ["cloud", "hide-hint"])
    result2 = runner.invoke(cli, ["cloud", "hide-hint"])
    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert cloud_hint._read_dismissed_at(isolated_state) is not None


def test_generate_suppresses_hint_after_hide_hint(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(cli, ["cloud", "hide-hint"])
    result = _invoke_generate(tmp_path)
    assert result.exit_code == 0
    assert "Docglow Cloud" not in result.output


def test_generate_resumes_hint_after_show_hint(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(cli, ["cloud", "hide-hint"])
    runner.invoke(cli, ["cloud", "show-hint"])
    result = _invoke_generate(tmp_path)
    assert result.exit_code == 0
    assert "Docglow Cloud" in result.output
