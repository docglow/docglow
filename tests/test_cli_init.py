"""Tests for docglow init command."""
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from docglow.cli import cli


class TestInitCommand:
    def test_creates_docglow_yml(self, tmp_path: Path) -> None:
        """init creates docglow.yml in the specified directory."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / "docglow.yml").exists()
        assert "Created" in result.output

    def test_generated_yaml_is_valid(self, tmp_path: Path) -> None:
        """Generated file is valid YAML."""
        runner = CliRunner()
        runner.invoke(cli, ["init", "--project-dir", str(tmp_path)])

        content = (tmp_path / "docglow.yml").read_text()
        parsed = yaml.safe_load(content)
        # Should be None or dict (all commented = None, uncommented = dict)
        assert parsed is None or isinstance(parsed, dict)

    def test_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        """init refuses to overwrite existing docglow.yml."""
        (tmp_path / "docglow.yml").write_text("existing: config")

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--project-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "already exists" in result.output
        # Original content preserved
        assert (tmp_path / "docglow.yml").read_text() == "existing: config"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        """init --force overwrites existing file."""
        (tmp_path / "docglow.yml").write_text("existing: config")

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--project-dir", str(tmp_path), "--force"])

        assert result.exit_code == 0
        assert (tmp_path / "docglow.yml").read_text() != "existing: config"

    def test_detects_yaml_extension(self, tmp_path: Path) -> None:
        """init detects existing docglow.yaml (not just .yml)."""
        (tmp_path / "docglow.yaml").write_text("existing: config")

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--project-dir", str(tmp_path)])

        assert "already exists" in result.output
