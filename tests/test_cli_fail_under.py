"""Tests for --fail-under CLI flag."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from docglow.cli import cli

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _mock_health_data(overall_score: float) -> dict:
    """Create mock health data with a given overall score."""
    return {
        "health": {
            "score": {
                "overall": overall_score,
                "grade": "A" if overall_score >= 90 else "B" if overall_score >= 80 else "C",
                "documentation": overall_score,
                "testing": overall_score,
                "freshness": 100.0,
                "complexity": 100.0,
                "naming": 100.0,
                "orphans": 100.0,
            },
            "coverage": {
                "models_documented": {"covered": 5, "total": 10},
                "columns_documented": {"covered": 20, "total": 40},
                "models_tested": {"covered": 5, "total": 10},
                "columns_tested": {"covered": 20, "total": 40},
            },
            "complexity": {"high_count": 0},
            "naming": {"compliant_count": 10, "total_checked": 10},
            "orphans": [],
        },
        "models": {},
        "sources": {},
        "metadata": {},
    }


def _make_mock_config() -> MagicMock:
    """Create a mock DocglowConfig with defaults."""
    config = MagicMock()
    config.ai.enabled = False
    config.title = "docglow"
    return config


class TestHealthFailUnder:
    """Tests for --fail-under on the health command."""

    def test_health_fail_under_exits_1_when_below(self, tmp_path: Path) -> None:
        """Health score below threshold should exit with code 1."""
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(60.0),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path), "--fail-under", "70"],
            )

        assert result.exit_code == 1
        assert "below" in result.output.lower()

    def test_health_fail_under_exits_0_when_above(self, tmp_path: Path) -> None:
        """Health score above threshold should exit with code 0."""
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(85.0),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path), "--fail-under", "70"],
            )

        assert result.exit_code == 0

    def test_health_no_fail_under_exits_0(self, tmp_path: Path) -> None:
        """Without --fail-under, health should always exit 0."""
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(30.0),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path)],
            )

        assert result.exit_code == 0


class TestGenerateFailUnder:
    """Tests for --fail-under on the generate command."""

    def test_generate_fail_under_exits_1_when_below(self, tmp_path: Path) -> None:
        """Generate with score below threshold should exit with code 1."""
        runner = CliRunner()
        with (
            patch("docglow.config.load_config", return_value=_make_mock_config()),
            patch(
                "docglow.generator.site.generate_site",
                return_value=tmp_path / "output",
            ),
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(60.0),
            ),
        ):
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path), "--fail-under", "70"],
            )

        assert result.exit_code == 1
        assert "below" in result.output.lower()

    def test_generate_fail_under_exits_0_when_above(self, tmp_path: Path) -> None:
        """Generate with score above threshold should exit with code 0."""
        runner = CliRunner()
        with (
            patch("docglow.config.load_config", return_value=_make_mock_config()),
            patch(
                "docglow.generator.site.generate_site",
                return_value=tmp_path / "output",
            ),
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(85.0),
            ),
        ):
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path), "--fail-under", "70"],
            )

        assert result.exit_code == 0
        assert "health score" in result.output.lower()
