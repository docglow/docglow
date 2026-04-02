"""Tests for column lineage default-on behavior (DOC-89)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from docglow.cli import cli


def _make_mock_config(*, column_lineage: bool = True) -> MagicMock:
    """Create a mock DocglowConfig with defaults."""
    config = MagicMock()
    config.ai.enabled = False
    config.title = "docglow"
    config.slim = False
    config.column_lineage = column_lineage
    return config


class TestColumnLineageDefaultOn:
    """Column lineage should run by default without any flag."""

    def test_column_lineage_enabled_by_default(self, tmp_path: Path) -> None:
        """generate without flags should pass column_lineage_enabled=True."""
        runner = CliRunner()
        captured: dict = {}

        def _capture_generate_site(**kwargs: object) -> tuple[Path, float]:
            captured.update(kwargs)
            return tmp_path / "out", 85.0

        with (
            patch("docglow.config.load_config", return_value=_make_mock_config()),
            patch("docglow.generator.site.generate_site", side_effect=_capture_generate_site),
            patch("docglow.cli.console"),
        ):
            # sqlglot must be importable for column lineage validation
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert captured["column_lineage_enabled"] is True

    def test_skip_column_lineage_flag_disables(self, tmp_path: Path) -> None:
        """--skip-column-lineage should pass column_lineage_enabled=False."""
        runner = CliRunner()
        captured: dict = {}

        def _capture_generate_site(**kwargs: object) -> tuple[Path, float]:
            captured.update(kwargs)
            return tmp_path / "out", 85.0

        with (
            patch("docglow.config.load_config", return_value=_make_mock_config()),
            patch("docglow.generator.site.generate_site", side_effect=_capture_generate_site),
            patch("docglow.cli.console"),
        ):
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path), "--skip-column-lineage"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert captured["column_lineage_enabled"] is False

    def test_config_column_lineage_false_disables(self, tmp_path: Path) -> None:
        """column_lineage: false in docglow.yml should disable column lineage."""
        runner = CliRunner()
        captured: dict = {}

        def _capture_generate_site(**kwargs: object) -> tuple[Path, float]:
            captured.update(kwargs)
            return tmp_path / "out", 85.0

        with (
            patch(
                "docglow.config.load_config",
                return_value=_make_mock_config(column_lineage=False),
            ),
            patch("docglow.generator.site.generate_site", side_effect=_capture_generate_site),
            patch("docglow.cli.console"),
        ):
            result = runner.invoke(
                cli,
                ["generate", "--project-dir", str(tmp_path)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert captured["column_lineage_enabled"] is False

    def test_column_lineage_select_overrides_skip(self, tmp_path: Path) -> None:
        """--column-lineage-select should enable lineage even with config disabled."""
        runner = CliRunner()
        captured: dict = {}

        def _capture_generate_site(**kwargs: object) -> tuple[Path, float]:
            captured.update(kwargs)
            return tmp_path / "out", 85.0

        with (
            patch(
                "docglow.config.load_config",
                return_value=_make_mock_config(column_lineage=False),
            ),
            patch("docglow.generator.site.generate_site", side_effect=_capture_generate_site),
            patch("docglow.cli.console"),
        ):
            result = runner.invoke(
                cli,
                [
                    "generate",
                    "--project-dir",
                    str(tmp_path),
                    "--column-lineage-select",
                    "fct_orders",
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert captured["column_lineage_enabled"] is True
        assert captured["column_lineage_select"] == "fct_orders"


class TestColumnLineageConfigParsing:
    """Test docglow.yml column_lineage field parsing."""

    def test_config_defaults_to_true(self) -> None:
        from docglow.config import DocglowConfig

        config = DocglowConfig()
        assert config.column_lineage is True

    def test_config_from_yaml_true(self, tmp_path: Path) -> None:
        config_file = tmp_path / "docglow.yml"
        config_file.write_text("version: 1\ncolumn_lineage: true\n")

        from docglow.config import load_config

        config = load_config(tmp_path)
        assert config.column_lineage is True

    def test_config_from_yaml_false(self, tmp_path: Path) -> None:
        config_file = tmp_path / "docglow.yml"
        config_file.write_text("version: 1\ncolumn_lineage: false\n")

        from docglow.config import load_config

        config = load_config(tmp_path)
        assert config.column_lineage is False

    def test_config_missing_defaults_true(self, tmp_path: Path) -> None:
        config_file = tmp_path / "docglow.yml"
        config_file.write_text("version: 1\n")

        from docglow.config import load_config

        config = load_config(tmp_path)
        assert config.column_lineage is True
