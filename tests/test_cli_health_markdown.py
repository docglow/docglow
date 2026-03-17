"""Tests for health --format markdown output."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from docglow.cli import cli


def _mock_health_data(
    overall: float = 85.0,
    *,
    undocumented_models: list | None = None,
    naming_violations: list | None = None,
    orphans: list | None = None,
) -> dict:
    """Create mock health data with configurable details."""
    return {
        "health": {
            "score": {
                "overall": overall,
                "grade": "A" if overall >= 90 else "B" if overall >= 80 else "C",
                "documentation": 80.0,
                "testing": 75.0,
                "freshness": 100.0,
                "complexity": 90.0,
                "naming": 95.0,
                "orphans": 100.0,
            },
            "coverage": {
                "models_documented": {"covered": 8, "total": 10},
                "columns_documented": {"covered": 30, "total": 40},
                "models_tested": {"covered": 7, "total": 10},
                "columns_tested": {"covered": 25, "total": 40},
                "undocumented_models": undocumented_models or [],
            },
            "complexity": {"high_count": 1},
            "naming": {
                "compliant_count": 9,
                "total_checked": 10,
                "violations": naming_violations or [],
            },
            "orphans": orphans or [],
        },
        "models": {},
        "sources": {},
        "metadata": {},
    }


class TestHealthMarkdownFormat:
    """Tests for --format markdown on the health command."""

    def test_health_format_markdown_outputs_table(self, tmp_path: Path) -> None:
        """--format markdown outputs a GitHub-flavored markdown table."""
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
                ["health", "--project-dir", str(tmp_path), "--format", "markdown"],
            )

        assert result.exit_code == 0
        assert "| Category | Score |" in result.output
        assert "Documentation" in result.output
        assert "/100" in result.output

    def test_health_format_markdown_contains_all_categories(self, tmp_path: Path) -> None:
        """Markdown output should include all health categories."""
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
                ["health", "--project-dir", str(tmp_path), "--format", "markdown"],
            )

        assert result.exit_code == 0
        categories = ["Documentation", "Testing", "Freshness", "Complexity", "Naming", "Orphans"]
        for category in categories:
            assert category in result.output

    def test_health_format_markdown_shows_undocumented_models(self, tmp_path: Path) -> None:
        """Markdown output should show undocumented model summary."""
        undoc = [
            {"name": "stg_orders", "downstream_count": 5},
            {"name": "stg_users", "downstream_count": 2},
        ]
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(70.0, undocumented_models=undoc),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path), "--format", "markdown"],
            )

        assert result.exit_code == 0
        assert "2 undocumented models" in result.output
        assert "stg_orders" in result.output

    def test_health_format_markdown_shows_naming_violations(self, tmp_path: Path) -> None:
        """Markdown output should show naming violation count."""
        violations = [{"model": "bad_name", "expected": "^stg_"}]
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(70.0, naming_violations=violations),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path), "--format", "markdown"],
            )

        assert result.exit_code == 0
        assert "1 naming violation" in result.output

    def test_health_format_markdown_shows_orphans(self, tmp_path: Path) -> None:
        """Markdown output should show orphan model count."""
        orphans = [{"name": "orphan_model"}]
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(70.0, orphans=orphans),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path), "--format", "markdown"],
            )

        assert result.exit_code == 0
        assert "1 orphan model" in result.output

    def test_health_format_markdown_fail_under_works(self, tmp_path: Path) -> None:
        """--fail-under should still work with markdown format."""
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
                [
                    "health",
                    "--project-dir",
                    str(tmp_path),
                    "--format",
                    "markdown",
                    "--fail-under",
                    "70",
                ],
            )

        assert result.exit_code == 1

    def test_health_format_markdown_no_issues_clean_output(self, tmp_path: Path) -> None:
        """When no issues exist, markdown should not show issue summaries."""
        runner = CliRunner()
        with (
            patch(
                "docglow.artifacts.loader.load_artifacts",
                return_value=MagicMock(),
            ),
            patch(
                "docglow.generator.data.build_docglow_data",
                return_value=_mock_health_data(95.0),
            ),
        ):
            result = runner.invoke(
                cli,
                ["health", "--project-dir", str(tmp_path), "--format", "markdown"],
            )

        assert result.exit_code == 0
        assert "undocumented" not in result.output
        assert "naming violation" not in result.output
        assert "orphan model" not in result.output
