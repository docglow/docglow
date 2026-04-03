"""Tests for CLI warning messages."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from docglow.cli import cli


class TestAiKeySecurityWarning:
    """DOC-10: AI mode info message."""

    def _make_mock_config(self) -> MagicMock:
        """Create a mock DocglowConfig with defaults."""
        config = MagicMock()
        config.ai.enabled = False
        config.title = "docglow"
        config.slim = False
        return config

    def test_ai_flag_prints_info_message(self, tmp_path: Path) -> None:
        """When --ai is used, an info message should confirm key is not embedded."""
        runner = CliRunner()
        with (
            patch("docglow.config.load_config", return_value=self._make_mock_config()),
            patch("docglow.generator.site.generate_site", side_effect=SystemExit(0)),
        ):
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path), "--ai"],
                catch_exceptions=False,
            )

        assert "not" in result.output.lower()
        assert "embedded" in result.output.lower()

    def test_no_ai_no_message(self, tmp_path: Path) -> None:
        """When --ai is NOT used, no AI info message should appear."""
        runner = CliRunner()
        with (
            patch("docglow.config.load_config", return_value=self._make_mock_config()),
            patch("docglow.generator.site.generate_site", side_effect=SystemExit(0)),
        ):
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path)],
                catch_exceptions=False,
            )

        assert "ai chat enabled" not in result.output.lower()
