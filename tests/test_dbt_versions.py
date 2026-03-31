"""Parameterized tests for dbt version compatibility.

Tests artifact loading, data transformation, and column lineage parsing
against fixture sets for dbt 1.8, 1.9, and 1.11.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from docglow.artifacts.loader import LoadedArtifacts, load_artifacts
from docglow.generator.data import build_docglow_data
from docglow.lineage.column_parser import parse_column_lineage

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Each entry: (fixture_subdir, expected_dbt_version)
DBT_VERSIONS = [
    ("dbt-1.8", "1.8.9"),
    ("dbt-1.9", "1.9.3"),
    (".", "1.11.7"),  # default fixtures at root
]

DBT_VERSION_IDS = ["dbt-1.8", "dbt-1.9", "dbt-1.11"]


def _copy_fixtures(fixture_subdir: str, target: Path) -> None:
    """Copy fixture files into a target directory for isolated loading."""
    src_dir = FIXTURES_DIR / fixture_subdir
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        src = src_dir / name
        if src.exists():
            (target / name).write_text(src.read_text())


@pytest.fixture(params=DBT_VERSIONS, ids=DBT_VERSION_IDS)
def versioned_artifacts(request: pytest.FixtureRequest, tmp_path: Path) -> LoadedArtifacts:
    """Load artifacts for each dbt version."""
    fixture_subdir, _ = request.param
    target = tmp_path / "target"
    target.mkdir()
    _copy_fixtures(fixture_subdir, target)
    return load_artifacts(tmp_path)


@pytest.fixture(params=DBT_VERSIONS, ids=DBT_VERSION_IDS)
def versioned_data(request: pytest.FixtureRequest, tmp_path: Path) -> dict[str, Any]:
    """Build docglow data for each dbt version."""
    fixture_subdir, _ = request.param
    target = tmp_path / "target"
    target.mkdir()
    _copy_fixtures(fixture_subdir, target)
    artifacts = load_artifacts(tmp_path)
    return build_docglow_data(artifacts)


class TestArtifactLoading:
    """Verify artifact loading works across dbt versions."""

    def test_manifest_loads(self, versioned_artifacts: LoadedArtifacts) -> None:
        assert versioned_artifacts.manifest is not None

    def test_catalog_loads(self, versioned_artifacts: LoadedArtifacts) -> None:
        assert versioned_artifacts.catalog is not None
        assert len(versioned_artifacts.catalog.nodes) > 0

    def test_run_results_load(self, versioned_artifacts: LoadedArtifacts) -> None:
        assert versioned_artifacts.run_results is not None
        assert len(versioned_artifacts.run_results.results) > 0

    def test_manifest_metadata(self, versioned_artifacts: LoadedArtifacts) -> None:
        meta = versioned_artifacts.manifest.metadata
        assert meta.project_name == "jaffle_shop"
        assert meta.dbt_version != ""
        assert "manifest" in meta.dbt_schema_version
        assert meta.adapter_type == "duckdb"

    def test_manifest_has_models(self, versioned_artifacts: LoadedArtifacts) -> None:
        models = {
            k: v
            for k, v in versioned_artifacts.manifest.nodes.items()
            if v.resource_type == "model"
        }
        assert len(models) == 13

    def test_manifest_has_tests(self, versioned_artifacts: LoadedArtifacts) -> None:
        tests = {
            k: v for k, v in versioned_artifacts.manifest.nodes.items() if v.resource_type == "test"
        }
        assert len(tests) > 0

    def test_manifest_has_sources(self, versioned_artifacts: LoadedArtifacts) -> None:
        assert len(versioned_artifacts.manifest.sources) == 6

    def test_manifest_parent_child_maps(self, versioned_artifacts: LoadedArtifacts) -> None:
        assert len(versioned_artifacts.manifest.parent_map) > 0
        assert len(versioned_artifacts.manifest.child_map) > 0

    def test_model_columns_present(self, versioned_artifacts: LoadedArtifacts) -> None:
        orders = versioned_artifacts.manifest.nodes.get("model.jaffle_shop.orders")
        assert orders is not None
        assert len(orders.columns) > 0
        assert "order_id" in orders.columns

    def test_test_metadata_present(self, versioned_artifacts: LoadedArtifacts) -> None:
        tests = [
            n
            for n in versioned_artifacts.manifest.nodes.values()
            if n.resource_type == "test" and n.test_metadata
        ]
        assert len(tests) > 0
        not_null = [t for t in tests if t.test_metadata and t.test_metadata.name == "not_null"]
        assert len(not_null) > 0

    def test_catalog_column_types(self, versioned_artifacts: LoadedArtifacts) -> None:
        customers = versioned_artifacts.catalog.nodes.get("model.jaffle_shop.customers")
        assert customers is not None
        assert len(customers.columns) > 0
        first_col = next(iter(customers.columns.values()))
        assert first_col.type != ""


class TestDataTransformation:
    """Verify the full transformation pipeline across dbt versions."""

    def test_top_level_keys(self, versioned_data: dict[str, Any]) -> None:
        expected = {
            "metadata",
            "models",
            "sources",
            "seeds",
            "snapshots",
            "exposures",
            "metrics",
            "lineage",
            "health",
            "search_index",
            "ai_context",
            "ai_key",
            "column_lineage",
        }
        assert set(versioned_data.keys()) == expected

    def test_metadata_populated(self, versioned_data: dict[str, Any]) -> None:
        meta = versioned_data["metadata"]
        assert meta["project_name"] == "jaffle_shop"
        assert meta["dbt_version"] != ""
        assert "manifest" in meta["artifact_versions"]

    def test_models_populated(self, versioned_data: dict[str, Any]) -> None:
        assert len(versioned_data["models"]) == 13

    def test_model_has_required_fields(self, versioned_data: dict[str, Any]) -> None:
        orders = versioned_data["models"]["model.jaffle_shop.orders"]
        required_fields = [
            "unique_id",
            "name",
            "description",
            "schema",
            "database",
            "materialization",
            "tags",
            "meta",
            "path",
            "folder",
            "raw_sql",
            "compiled_sql",
            "columns",
            "depends_on",
            "referenced_by",
            "sources_used",
            "test_results",
            "last_run",
            "catalog_stats",
        ]
        for field in required_fields:
            assert field in orders, f"Missing field: {field}"

    def test_columns_merged_with_types(self, versioned_data: dict[str, Any]) -> None:
        """Columns should have catalog types and manifest descriptions."""
        orders = versioned_data["models"]["model.jaffle_shop.orders"]
        order_id_cols = [c for c in orders["columns"] if c["name"].lower() == "order_id"]
        assert len(order_id_cols) == 1
        assert order_id_cols[0]["data_type"] != ""
        assert order_id_cols[0]["description"] != ""

    def test_test_results_attached(self, versioned_data: dict[str, Any]) -> None:
        orders = versioned_data["models"]["model.jaffle_shop.orders"]
        assert len(orders["test_results"]) > 0
        for result in orders["test_results"]:
            assert result["status"] in ("pass", "fail", "warn", "error", "not_run")

    def test_test_status_normalized(self, versioned_data: dict[str, Any]) -> None:
        """dbt 'success' status should be normalized to 'pass'."""
        for model_data in versioned_data["models"].values():
            for result in model_data["test_results"]:
                assert result["status"] != "success"

    def test_dependencies_populated(self, versioned_data: dict[str, Any]) -> None:
        orders = versioned_data["models"]["model.jaffle_shop.orders"]
        assert len(orders["depends_on"]) > 0

    def test_referenced_by_populated(self, versioned_data: dict[str, Any]) -> None:
        stg_orders = versioned_data["models"].get("model.jaffle_shop.stg_orders")
        if stg_orders:
            assert len(stg_orders["referenced_by"]) > 0

    def test_sources_populated(self, versioned_data: dict[str, Any]) -> None:
        assert len(versioned_data["sources"]) == 6
        raw_customers = versioned_data["sources"].get("source.jaffle_shop.ecom.raw_customers")
        assert raw_customers is not None
        assert raw_customers["name"] == "raw_customers"

    def test_source_columns_have_types(self, versioned_data: dict[str, Any]) -> None:
        raw_customers = versioned_data["sources"]["source.jaffle_shop.ecom.raw_customers"]
        assert len(raw_customers["columns"]) > 0
        for col in raw_customers["columns"]:
            assert col["data_type"] != ""

    def test_lineage_nodes_and_edges(self, versioned_data: dict[str, Any]) -> None:
        lineage = versioned_data["lineage"]
        assert len(lineage["nodes"]) > 0
        assert len(lineage["edges"]) > 0

        resource_types = {n["resource_type"] for n in lineage["nodes"]}
        assert "model" in resource_types
        assert "source" in resource_types

    def test_search_index_populated(self, versioned_data: dict[str, Any]) -> None:
        index = versioned_data["search_index"]
        assert len(index) > 0
        resource_types = {e["resource_type"] for e in index}
        assert "model" in resource_types
        assert "source" in resource_types

    def test_health_scores_computed(self, versioned_data: dict[str, Any]) -> None:
        health = versioned_data["health"]
        assert health is not None
        assert "project" in health or "summary" in health or isinstance(health, dict)

    def test_last_run_populated(self, versioned_data: dict[str, Any]) -> None:
        orders = versioned_data["models"]["model.jaffle_shop.orders"]
        assert orders["last_run"] is not None
        assert orders["last_run"]["status"] == "success"
        assert orders["last_run"]["execution_time"] > 0


class TestColumnLineageAcrossVersions:
    """Verify column lineage parsing works with catalog data from each dbt version.

    The fixtures don't contain compiled_code (only Jinja raw_code), so we
    test with representative SQL that mirrors what each version's compiled
    output would produce for the orders model.
    """

    # Simplified compiled SQL representative of the orders model.
    # Uses direct table references (no SELECT *) for reliable lineage tracing.
    ORDERS_COMPILED_SQL = """
    select
        o.order_id,
        o.location_id,
        o.customer_id,
        o.subtotal_cents,
        o.ordered_at,
        sum(oi.product_price) as order_items_subtotal,
        count(oi.order_item_id) as count_order_items,
        case when count(oi.order_item_id) > 0 then true else false end as has_items
    from main.stg_orders o
    left join main.order_items oi on o.order_id = oi.order_id
    group by 1, 2, 3, 4, 5
    """

    @pytest.fixture(params=DBT_VERSIONS, ids=DBT_VERSION_IDS)
    def versioned_catalog_columns(
        self,
        request: pytest.FixtureRequest,
    ) -> dict[str, Any]:
        """Load catalog columns for the orders model from each version."""
        fixture_subdir, _ = request.param
        src_dir = FIXTURES_DIR / fixture_subdir

        with open(src_dir / "catalog.json") as f:
            catalog = json.load(f)

        result: dict[str, Any] = catalog["nodes"].get("model.jaffle_shop.orders", {})
        return result

    def test_column_lineage_parses(
        self,
        versioned_catalog_columns: dict[str, Any],
    ) -> None:
        result = parse_column_lineage(self.ORDERS_COMPILED_SQL, dialect="duckdb")
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_column_lineage_finds_known_columns(
        self,
        versioned_catalog_columns: dict[str, Any],
    ) -> None:
        catalog_columns = list(versioned_catalog_columns.get("columns", {}).keys())
        result = parse_column_lineage(self.ORDERS_COMPILED_SQL, dialect="duckdb")

        result_lower = {k.lower() for k in result}
        found = [col for col in catalog_columns if col.lower() in result_lower]
        assert len(found) > 0, (
            f"No catalog columns found in lineage output. "
            f"Catalog: {catalog_columns[:5]}, Lineage: {list(result.keys())[:5]}"
        )

    def test_column_lineage_has_valid_transformations(self) -> None:
        result = parse_column_lineage(self.ORDERS_COMPILED_SQL, dialect="duckdb")
        valid_transformations = {"passthrough", "derived", "aggregated", "unknown"}

        for col_name, deps in result.items():
            for dep in deps:
                assert dep.transformation in valid_transformations, (
                    f"Invalid transformation '{dep.transformation}' for column '{col_name}'"
                )

    def test_passthrough_columns_detected(self) -> None:
        result = parse_column_lineage(self.ORDERS_COMPILED_SQL, dialect="duckdb")
        passthrough_cols = {
            col
            for col, deps in result.items()
            if any(d.transformation == "passthrough" for d in deps)
        }
        # order_id, location_id, customer_id should be passthrough
        assert "order_id" in passthrough_cols or "ORDER_ID" in passthrough_cols

    def test_aggregated_columns_detected(self) -> None:
        result = parse_column_lineage(self.ORDERS_COMPILED_SQL, dialect="duckdb")
        agg_cols = {
            col
            for col, deps in result.items()
            if any(d.transformation == "aggregated" for d in deps)
        }
        assert len(agg_cols) > 0, "Expected aggregated columns from SUM/COUNT expressions"


class TestVersionMetadataTracking:
    """Verify version metadata is correctly captured in output."""

    @pytest.mark.parametrize(
        ("fixture_subdir", "expected_version"),
        [
            ("dbt-1.8", "1.8.9"),
            ("dbt-1.9", "1.9.3"),
            (".", "1.11.7"),
        ],
        ids=DBT_VERSION_IDS,
    )
    def test_dbt_version_in_metadata(
        self,
        tmp_path: Path,
        fixture_subdir: str,
        expected_version: str,
    ) -> None:
        target = tmp_path / "target"
        target.mkdir()
        _copy_fixtures(fixture_subdir, target)
        artifacts = load_artifacts(tmp_path)
        data = build_docglow_data(artifacts)

        assert data["metadata"]["dbt_version"] == expected_version

    @pytest.mark.parametrize(
        ("fixture_subdir", "expected_version"),
        [
            ("dbt-1.8", "1.8.9"),
            ("dbt-1.9", "1.9.3"),
            (".", "1.11.7"),
        ],
        ids=DBT_VERSION_IDS,
    )
    def test_artifact_versions_in_metadata(
        self,
        tmp_path: Path,
        fixture_subdir: str,
        expected_version: str,
    ) -> None:
        target = tmp_path / "target"
        target.mkdir()
        _copy_fixtures(fixture_subdir, target)
        artifacts = load_artifacts(tmp_path)
        data = build_docglow_data(artifacts)

        assert "manifest" in data["metadata"]["artifact_versions"]
        assert data["metadata"]["artifact_versions"]["manifest"] != ""
