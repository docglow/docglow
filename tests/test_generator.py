"""Tests for the site generator and bundler."""

import json
from pathlib import Path

from docglow.artifacts.loader import load_artifacts
from docglow.generator.bundle import bundle_site
from docglow.generator.data import build_docglow_data
from docglow.generator.site import generate_site

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _setup_target(tmp_path: Path) -> Path:
    """Copy fixture artifacts into a target directory."""
    target = tmp_path / "target"
    target.mkdir()
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        src = FIXTURES_DIR / name
        if src.exists():
            (target / name).write_text(src.read_text())
    return tmp_path


class TestBundleSite:
    """Test the bundler that combines frontend + data."""

    def test_bundle_separate_creates_data_file(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        docglow_data = build_docglow_data(artifacts)

        output = tmp_path / "output"
        bundle_site(docglow_data, output, static=False)

        data_file = output / "docglow-data.json"
        assert data_file.exists()

        loaded = json.loads(data_file.read_text())
        assert "metadata" in loaded
        assert "models" in loaded

    def test_bundle_separate_copies_index(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        docglow_data = build_docglow_data(artifacts)

        output = tmp_path / "output"
        bundle_site(docglow_data, output, static=False)

        assert (output / "index.html").exists()

    def test_bundle_static_creates_single_file(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        docglow_data = build_docglow_data(artifacts)

        output = tmp_path / "output_static"
        bundle_site(docglow_data, output, static=True)

        index = output / "index.html"
        assert index.exists()

        html = index.read_text()
        assert "window.__DOCGLOW_DATA__=" in html
        assert "jaffle_shop" in html

    def test_bundle_static_no_separate_data_file(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        docglow_data = build_docglow_data(artifacts)

        output = tmp_path / "output_static"
        bundle_site(docglow_data, output, static=True)

        assert not (output / "docglow-data.json").exists()

    def test_data_json_valid(self, tmp_path: Path) -> None:
        """The output docglow-data.json is valid JSON with expected structure."""
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        docglow_data = build_docglow_data(artifacts)

        output = tmp_path / "output"
        bundle_site(docglow_data, output, static=False)

        data = json.loads((output / "docglow-data.json").read_text())

        assert data["metadata"]["project_name"] == "jaffle_shop"
        assert len(data["models"]) > 0
        assert len(data["sources"]) > 0
        assert len(data["lineage"]["nodes"]) > 0
        assert len(data["lineage"]["edges"]) > 0
        assert len(data["search_index"]) > 0


class TestGenerateSite:
    """Test the full generate_site orchestrator."""

    def test_generate_creates_output_dir(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        output = tmp_path / "custom_output"

        result, score = generate_site(project, output_dir=output)

        assert result == output
        assert output.exists()
        assert (output / "docglow-data.json").exists()
        assert isinstance(score, float)

    def test_generate_default_output_dir(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)

        result, _score = generate_site(project)

        assert result == project / "target" / "docglow"
        assert (result / "docglow-data.json").exists()

    def test_generate_static_mode(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        output = tmp_path / "static_out"

        generate_site(project, output_dir=output, static=True)

        index = output / "index.html"
        assert index.exists()
        html = index.read_text()
        assert "window.__DOCGLOW_DATA__=" in html

    def test_generate_custom_title(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        output = tmp_path / "titled"

        generate_site(project, output_dir=output, title="My Custom Docs")

        data = json.loads((output / "docglow-data.json").read_text())
        assert data["metadata"]["project_name"] == "My Custom Docs"


class TestSlimFlag:
    """Test the --slim flag strips SQL from output."""

    def test_slim_strips_sql_from_models(self, tmp_path: Path) -> None:
        """With --slim, raw_sql and compiled_sql should be empty strings."""
        project = _setup_target(tmp_path)
        output = tmp_path / "slim_output"

        generate_site(project, output_dir=output, slim=True)

        data = json.loads((output / "docglow-data.json").read_text())
        for model in data["models"].values():
            assert model["raw_sql"] == "", f"raw_sql not stripped for {model['name']}"
            assert model["compiled_sql"] == "", f"compiled_sql not stripped for {model['name']}"

    def test_slim_strips_sql_from_seeds(self, tmp_path: Path) -> None:
        """With --slim, seeds should also have empty SQL fields."""
        project = _setup_target(tmp_path)
        output = tmp_path / "slim_output"

        generate_site(project, output_dir=output, slim=True)

        data = json.loads((output / "docglow-data.json").read_text())
        for seed in data["seeds"].values():
            assert seed["raw_sql"] == ""
            assert seed["compiled_sql"] == ""

    def test_slim_preserves_non_sql_fields(self, tmp_path: Path) -> None:
        """--slim should not affect non-SQL model fields."""
        project = _setup_target(tmp_path)
        output = tmp_path / "slim_output"

        generate_site(project, output_dir=output, slim=True)

        data = json.loads((output / "docglow-data.json").read_text())
        for model in data["models"].values():
            assert model["name"]
            assert model["unique_id"]
            assert "columns" in model
            assert "depends_on" in model

    def test_slim_preserves_lineage(self, tmp_path: Path) -> None:
        """Lineage should still be built correctly with --slim."""
        project = _setup_target(tmp_path)
        output = tmp_path / "slim_output"

        generate_site(project, output_dir=output, slim=True)

        data = json.loads((output / "docglow-data.json").read_text())
        assert len(data["lineage"]["nodes"]) > 0
        assert len(data["lineage"]["edges"]) > 0

    def test_slim_reduces_file_size(self, tmp_path: Path) -> None:
        """--slim output should be smaller than default output."""
        project = _setup_target(tmp_path)
        normal_output = tmp_path / "normal"
        slim_output = tmp_path / "slim"

        generate_site(project, output_dir=normal_output)
        generate_site(project, output_dir=slim_output, slim=True)

        normal_size = (normal_output / "docglow-data.json").stat().st_size
        slim_size = (slim_output / "docglow-data.json").stat().st_size
        assert slim_size < normal_size, (
            f"Slim output ({slim_size}) should be smaller than normal ({normal_size})"
        )

    def test_without_slim_sql_is_present(self, tmp_path: Path) -> None:
        """Without --slim, SQL fields should contain actual SQL."""
        project = _setup_target(tmp_path)
        output = tmp_path / "normal_output"

        generate_site(project, output_dir=output)

        data = json.loads((output / "docglow-data.json").read_text())
        has_sql = any(model.get("raw_sql", "") != "" for model in data["models"].values())
        assert has_sql, "Without --slim, at least some models should have SQL"
