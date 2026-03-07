"""Tests for the site generator and bundler."""

import json
from pathlib import Path

import pytest

from docs_plus_plus.artifacts.loader import load_artifacts
from docs_plus_plus.generator.bundle import bundle_site
from docs_plus_plus.generator.data import build_datum_data
from docs_plus_plus.generator.site import generate_site


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
        datum_data = build_datum_data(artifacts)

        output = tmp_path / "output"
        bundle_site(datum_data, output, static=False)

        data_file = output / "datum-data.json"
        assert data_file.exists()

        loaded = json.loads(data_file.read_text())
        assert "metadata" in loaded
        assert "models" in loaded

    def test_bundle_separate_copies_index(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        datum_data = build_datum_data(artifacts)

        output = tmp_path / "output"
        bundle_site(datum_data, output, static=False)

        assert (output / "index.html").exists()

    def test_bundle_static_creates_single_file(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        datum_data = build_datum_data(artifacts)

        output = tmp_path / "output_static"
        bundle_site(datum_data, output, static=True)

        index = output / "index.html"
        assert index.exists()

        html = index.read_text()
        assert "window.__DATUM_DATA__=" in html
        assert "jaffle_shop" in html

    def test_bundle_static_no_separate_data_file(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        datum_data = build_datum_data(artifacts)

        output = tmp_path / "output_static"
        bundle_site(datum_data, output, static=True)

        assert not (output / "datum-data.json").exists()

    def test_data_json_valid(self, tmp_path: Path) -> None:
        """The output datum-data.json is valid JSON with expected structure."""
        project = _setup_target(tmp_path)
        artifacts = load_artifacts(project)
        datum_data = build_datum_data(artifacts)

        output = tmp_path / "output"
        bundle_site(datum_data, output, static=False)

        data = json.loads((output / "datum-data.json").read_text())

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

        result = generate_site(project, output_dir=output)

        assert result == output
        assert output.exists()
        assert (output / "datum-data.json").exists()

    def test_generate_default_output_dir(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)

        result = generate_site(project)

        assert result == project / "target" / "datum"
        assert (result / "datum-data.json").exists()

    def test_generate_static_mode(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        output = tmp_path / "static_out"

        generate_site(project, output_dir=output, static=True)

        index = output / "index.html"
        assert index.exists()
        html = index.read_text()
        assert "window.__DATUM_DATA__=" in html

    def test_generate_custom_title(self, tmp_path: Path) -> None:
        project = _setup_target(tmp_path)
        output = tmp_path / "titled"

        generate_site(project, output_dir=output, title="My Custom Docs")

        data = json.loads((output / "datum-data.json").read_text())
        assert data["metadata"]["project_name"] == "My Custom Docs"
