"""Tests for artifact loading and parsing."""

import logging
from pathlib import Path

import pytest

from docglow.artifacts.catalog import CatalogNode, CatalogStat
from docglow.artifacts.loader import ArtifactLoadError, LoadedArtifacts, load_artifacts
from docglow.artifacts.manifest import ManifestExposure

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCatalogStatNulls:
    """Adapters like Databricks emit null stat fields; parsing must tolerate them."""

    def test_null_value_and_description(self) -> None:
        """Databricks reports bytes/rows stats with null value and description."""
        stat = CatalogStat.model_validate(
            {"id": "bytes", "label": "Size", "value": None, "include": True, "description": None}
        )
        assert stat.value is None
        assert stat.description == ""

    def test_null_label_and_include(self) -> None:
        stat = CatalogStat.model_validate(
            {"id": "rows", "label": None, "value": 42, "include": None, "description": None}
        )
        assert stat.label == ""
        assert stat.include is False
        assert stat.value == 42

    def test_catalog_node_with_databricks_style_stats(self) -> None:
        node = CatalogNode.model_validate(
            {
                "unique_id": "model.jaffle_shop.orders",
                "metadata": {"type": "table", "schema": "main", "name": "orders"},
                "columns": {},
                "stats": {
                    "bytes": {
                        "id": "bytes",
                        "label": "bytes",
                        "value": None,
                        "include": True,
                        "description": None,
                    },
                    "rows": {
                        "id": "rows",
                        "label": "rows",
                        "value": None,
                        "include": True,
                        "description": None,
                    },
                    "has_stats": {
                        "id": "has_stats",
                        "label": "Has Stats?",
                        "value": True,
                        "include": False,
                        "description": "Indicates whether there are statistics for this table",
                    },
                },
            }
        )
        assert node.stats["bytes"].value is None
        assert node.stats["rows"].value is None
        assert node.stats["has_stats"].value is True


class TestManifestExposureOwner:
    """Exposure owner fields are optional in dbt; nulls must not break parsing."""

    def test_owner_name_null(self) -> None:
        """dbt writes owner.name as null when only email is set."""
        exposure = ManifestExposure(
            unique_id="exposure.jaffle_shop.dashboard",
            name="dashboard",
            owner={"name": None, "email": "data@example.com"},
        )
        assert exposure.owner == {"email": "data@example.com"}

    def test_owner_email_null(self) -> None:
        exposure = ManifestExposure(
            unique_id="exposure.jaffle_shop.dashboard",
            name="dashboard",
            owner={"name": "Data Team", "email": None},
        )
        assert exposure.owner == {"name": "Data Team"}

    def test_owner_all_null(self) -> None:
        exposure = ManifestExposure(
            unique_id="exposure.jaffle_shop.dashboard",
            name="dashboard",
            owner={"name": None, "email": None},
        )
        assert exposure.owner == {}

    def test_owner_missing(self) -> None:
        exposure = ManifestExposure(
            unique_id="exposure.jaffle_shop.dashboard",
            name="dashboard",
        )
        assert exposure.owner == {}


class TestLoadArtifacts:
    """Test loading artifacts from the fixtures directory."""

    def test_load_all_artifacts(self, tmp_path: Path) -> None:
        """Load manifest, catalog, and run_results from fixtures."""
        # Symlink fixture files into a fake target dir
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json", "run_results.json"):
            src = FIXTURES_DIR / name
            if src.exists():
                (target / name).write_text(src.read_text())

        result = load_artifacts(tmp_path)

        assert isinstance(result, LoadedArtifacts)
        assert result.manifest is not None
        assert result.catalog is not None
        assert result.run_results is not None
        assert result.source_freshness is None  # No sources.json in fixtures

    def test_manifest_metadata(self, tmp_path: Path) -> None:
        """Manifest metadata is parsed correctly."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert result.manifest.metadata.project_name == "jaffle_shop"
        assert result.manifest.metadata.dbt_version != ""
        assert "manifest" in result.manifest.metadata.dbt_schema_version

    def test_manifest_models_parsed(self, tmp_path: Path) -> None:
        """Manifest nodes include models with expected fields."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        models = {k: v for k, v in result.manifest.nodes.items() if v.resource_type == "model"}
        assert len(models) > 0

        # Check a known model
        orders = models.get("model.jaffle_shop.orders")
        assert orders is not None
        assert orders.name == "orders"
        assert orders.description != ""
        assert len(orders.columns) > 0
        assert "order_id" in orders.columns
        assert orders.columns["order_id"].description != ""

    def test_manifest_sources_parsed(self, tmp_path: Path) -> None:
        """Manifest sources are parsed correctly."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert len(result.manifest.sources) > 0
        raw_customers = result.manifest.sources.get("source.jaffle_shop.ecom.raw_customers")
        assert raw_customers is not None
        assert raw_customers.name == "raw_customers"
        assert raw_customers.source_name == "ecom"

    def test_manifest_tests_parsed(self, tmp_path: Path) -> None:
        """Manifest test nodes have test_metadata."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        tests = {k: v for k, v in result.manifest.nodes.items() if v.resource_type == "test"}
        assert len(tests) > 0

        # Find a not_null test
        not_null_tests = [
            t for t in tests.values() if t.test_metadata and t.test_metadata.name == "not_null"
        ]
        assert len(not_null_tests) > 0
        assert not_null_tests[0].column_name is not None

    def test_manifest_parent_child_maps(self, tmp_path: Path) -> None:
        """Parent and child maps are populated."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert len(result.manifest.parent_map) > 0
        assert len(result.manifest.child_map) > 0

    def test_catalog_nodes_parsed(self, tmp_path: Path) -> None:
        """Catalog nodes have columns with types."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert len(result.catalog.nodes) > 0

        # Find the customers catalog entry
        customers = result.catalog.nodes.get("model.jaffle_shop.customers")
        assert customers is not None
        assert len(customers.columns) > 0

        # Check column has a type
        first_col = next(iter(customers.columns.values()))
        assert first_col.type != ""

    def test_catalog_sources_parsed(self, tmp_path: Path) -> None:
        """Catalog sources are parsed."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert len(result.catalog.sources) > 0

    def test_run_results_parsed(self, tmp_path: Path) -> None:
        """Run results contain test and model results."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json", "run_results.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert result.run_results is not None
        assert len(result.run_results.results) > 0

        # Check a test result
        test_results = [r for r in result.run_results.results if "test." in r.unique_id]
        assert len(test_results) > 0
        assert test_results[0].status in ("success", "fail", "error", "warn", "pass")

    def test_missing_target_dir_raises(self, tmp_path: Path) -> None:
        """Missing target directory raises ArtifactLoadError."""
        with pytest.raises(ArtifactLoadError, match="Target directory not found"):
            load_artifacts(tmp_path)

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        """Missing manifest.json raises ArtifactLoadError."""
        target = tmp_path / "target"
        target.mkdir()

        with pytest.raises(ArtifactLoadError, match="manifest.json"):
            load_artifacts(tmp_path)

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        """Invalid JSON raises ArtifactLoadError with clear message."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "manifest.json").write_text("{invalid json")

        with pytest.raises(ArtifactLoadError, match="Invalid JSON"):
            load_artifacts(tmp_path)

    def test_missing_optional_artifacts_ok(self, tmp_path: Path) -> None:
        """Missing run_results and sources produce warnings, not errors."""
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (target / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path)

        assert result.run_results is None
        assert result.source_freshness is None

    def test_custom_target_dir(self, tmp_path: Path) -> None:
        """Custom target directory path works."""
        custom = tmp_path / "custom_output"
        custom.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (custom / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path, target_dir=Path("custom_output"))

        assert result.manifest is not None

    def test_absolute_target_dir(self, tmp_path: Path) -> None:
        """Absolute target directory path works."""
        custom = tmp_path / "abs_target"
        custom.mkdir()
        for name in ("manifest.json", "catalog.json"):
            (custom / name).write_text((FIXTURES_DIR / name).read_text())

        result = load_artifacts(tmp_path, target_dir=custom)

        assert result.manifest is not None

    def test_missing_catalog_degrades_gracefully(self, tmp_path: Path) -> None:
        """Missing catalog.json should not raise — creates empty catalog."""
        target = tmp_path / "target"
        target.mkdir()
        # Only copy manifest, NOT catalog
        (target / "manifest.json").write_text((FIXTURES_DIR / "manifest.json").read_text())

        result = load_artifacts(tmp_path)

        assert result.manifest is not None
        assert result.catalog is not None
        assert len(result.catalog.nodes) == 0
        assert len(result.catalog.sources) == 0

    def test_missing_catalog_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing catalog.json logs a specific warning."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "manifest.json").write_text((FIXTURES_DIR / "manifest.json").read_text())

        with caplog.at_level(logging.WARNING):
            load_artifacts(tmp_path)

        assert "catalog.json not found" in caplog.text
        assert "column types will be unavailable" in caplog.text

    def test_missing_manifest_actionable_error(self, tmp_path: Path) -> None:
        """Missing manifest.json gives actionable error message."""
        target = tmp_path / "target"
        target.mkdir()

        with pytest.raises(ArtifactLoadError, match="dbt compile") as exc_info:
            load_artifacts(tmp_path)

        error_msg = str(exc_info.value)
        assert "manifest.json" in error_msg
        assert "dbt compile" in error_msg
        assert "dbt run" in error_msg
        assert "--target-dir" in error_msg
