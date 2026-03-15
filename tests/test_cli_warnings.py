"""Tests for CLI warning messages."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from docglow.cli import cli


class TestAiKeySecurityWarning:
    """DOC-10: AI key security warning."""

    def _make_mock_config(self) -> MagicMock:
        """Create a mock DocglowConfig with defaults."""
        config = MagicMock()
        config.ai.enabled = False
        config.title = "docglow"
        return config

    def test_ai_flag_prints_security_warning(self, tmp_path: Path) -> None:
        """When --ai is used, a security warning should be printed."""
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

        assert "api key" in result.output.lower()
        assert "do not deploy" in result.output.lower()

    def test_ai_key_flag_prints_security_warning(self, tmp_path: Path) -> None:
        """When --ai-key is used, a security warning should be printed."""
        runner = CliRunner()
        with (
            patch("docglow.config.load_config", return_value=self._make_mock_config()),
            patch("docglow.generator.site.generate_site", side_effect=SystemExit(0)),
        ):
            result = runner.invoke(
                cli,
                [
                    "generate",
                    "--project-dir",
                    str(tmp_path),
                    "--ai-key",
                    "sk-test-fake-key",
                ],
                catch_exceptions=False,
            )

        assert "api key" in result.output.lower()

    def test_no_ai_no_warning(self, tmp_path: Path) -> None:
        """When --ai is NOT used, no security warning should appear."""
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

        assert "api key" not in result.output.lower()
