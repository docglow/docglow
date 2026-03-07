"""Tests for the data transformer (artifacts -> DatumData payload)."""

from pathlib import Path

import pytest

from docs_plus_plus.artifacts.loader import load_artifacts
from docs_plus_plus.generator.data import build_datum_data


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures(tmp_path: Path) -> dict:
    """Helper to load fixtures and build datum data."""
    target = tmp_path / "target"
    target.mkdir()
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        src = FIXTURES_DIR / name
        if src.exists():
            (target / name).write_text(src.read_text())

    artifacts = load_artifacts(tmp_path)
    return build_datum_data(artifacts)


class TestBuildDatumData:
    """Test the full data transformation pipeline."""

    def test_top_level_keys(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)

        expected_keys = {
            "metadata", "models", "sources", "seeds", "snapshots",
            "exposures", "metrics", "lineage", "health", "search_index",
            "ai_context",
        }
        assert set(data.keys()) == expected_keys

    def test_metadata(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        meta = data["metadata"]

        assert meta["project_name"] == "jaffle_shop"
        assert meta["dbt_version"] != ""
        assert meta["docs_plus_plus_version"] == "0.1.0"
        assert meta["profiling_enabled"] is False
        assert meta["ai_enabled"] is False
        assert "manifest" in meta["artifact_versions"]

    def test_models_populated(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)

        assert len(data["models"]) > 0
        # Check a known model
        orders = data["models"].get("model.jaffle_shop.orders")
        assert orders is not None
        assert orders["name"] == "orders"

    def test_model_has_required_fields(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]

        required_fields = [
            "unique_id", "name", "description", "schema", "database",
            "materialization", "tags", "meta", "path", "folder",
            "raw_sql", "compiled_sql", "columns", "depends_on",
            "referenced_by", "sources_used", "test_results", "last_run",
            "catalog_stats",
        ]
        for field in required_fields:
            assert field in orders, f"Missing field: {field}"

    def test_model_description(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]

        assert orders["description"] != ""
        assert "order" in orders["description"].lower()

    def test_model_columns_merged(self, tmp_path: Path) -> None:
        """Columns should have both catalog types and manifest descriptions."""
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]
        columns = orders["columns"]

        assert len(columns) > 0

        # Find order_id column
        order_id_cols = [c for c in columns if c["name"].lower() == "order_id"]
        assert len(order_id_cols) == 1
        order_id = order_id_cols[0]

        # Should have type from catalog
        assert order_id["data_type"] != ""
        # Should have description from manifest
        assert order_id["description"] != ""

    def test_model_column_tests(self, tmp_path: Path) -> None:
        """Columns should have test information."""
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]
        columns = orders["columns"]

        order_id = next(c for c in columns if c["name"].lower() == "order_id")
        assert len(order_id["tests"]) > 0

        test_types = {t["test_type"] for t in order_id["tests"]}
        assert "not_null" in test_types or "unique" in test_types

    def test_model_test_results(self, tmp_path: Path) -> None:
        """Model should have test results with statuses."""
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]

        assert len(orders["test_results"]) > 0
        for result in orders["test_results"]:
            assert result["status"] in ("pass", "fail", "warn", "error", "not_run")
            assert result["test_name"] != ""

    def test_model_dependencies(self, tmp_path: Path) -> None:
        """Model should have upstream dependencies."""
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]

        assert len(orders["depends_on"]) > 0

    def test_model_referenced_by(self, tmp_path: Path) -> None:
        """Models that are depended upon should have referenced_by populated."""
        data = _load_fixtures(tmp_path)

        # stg_orders should be referenced by orders (at minimum)
        stg_orders = data["models"].get("model.jaffle_shop.stg_orders")
        if stg_orders:
            assert len(stg_orders["referenced_by"]) > 0

    def test_model_last_run(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]

        assert orders["last_run"] is not None
        assert orders["last_run"]["status"] == "success"
        assert orders["last_run"]["execution_time"] > 0

    def test_model_path_and_folder(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        orders = data["models"]["model.jaffle_shop.orders"]

        assert orders["path"] != ""
        assert orders["folder"] != ""

    def test_sources_populated(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)

        assert len(data["sources"]) > 0
        raw_customers = data["sources"].get("source.jaffle_shop.ecom.raw_customers")
        assert raw_customers is not None
        assert raw_customers["name"] == "raw_customers"
        assert raw_customers["source_name"] == "ecom"

    def test_source_columns(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        raw_customers = data["sources"]["source.jaffle_shop.ecom.raw_customers"]

        assert len(raw_customers["columns"]) > 0
        for col in raw_customers["columns"]:
            assert col["data_type"] != ""

    def test_lineage_nodes_and_edges(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        lineage = data["lineage"]

        assert len(lineage["nodes"]) > 0
        assert len(lineage["edges"]) > 0

        # Check node structure
        node = lineage["nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "resource_type" in node

        # Check edge structure
        edge = lineage["edges"][0]
        assert "source" in edge
        assert "target" in edge

    def test_lineage_has_sources_and_models(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        lineage = data["lineage"]

        resource_types = {n["resource_type"] for n in lineage["nodes"]}
        assert "model" in resource_types
        assert "source" in resource_types

    def test_search_index(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        search_index = data["search_index"]

        assert len(search_index) > 0

        entry = search_index[0]
        assert "unique_id" in entry
        assert "name" in entry
        assert "resource_type" in entry
        assert "description" in entry
        assert "columns" in entry

    def test_search_index_covers_models_and_sources(self, tmp_path: Path) -> None:
        data = _load_fixtures(tmp_path)
        search_index = data["search_index"]

        resource_types = {e["resource_type"] for e in search_index}
        assert "model" in resource_types
        assert "source" in resource_types

    def test_test_status_normalization(self, tmp_path: Path) -> None:
        """dbt uses 'success' for passing tests, we normalize to 'pass'."""
        data = _load_fixtures(tmp_path)

        for model_data in data["models"].values():
            for result in model_data["test_results"]:
                assert result["status"] != "success", (
                    f"Test status 'success' should be normalized to 'pass'"
                )

    def test_no_test_nodes_in_models(self, tmp_path: Path) -> None:
        """Test nodes should not appear in the models dict."""
        data = _load_fixtures(tmp_path)

        for uid in data["models"]:
            assert not uid.startswith("test."), f"Test node in models: {uid}"
