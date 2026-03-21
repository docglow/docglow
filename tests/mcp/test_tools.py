"""Tests for MCP tool functions."""

from __future__ import annotations

import pytest

from docglow.mcp.tools import TOOL_MAP, TOOLS


@pytest.fixture()
def sample_data() -> dict:
    """Minimal docglow data payload for testing."""
    return {
        "models": {
            "model.jaffle_shop.stg_orders": {
                "unique_id": "model.jaffle_shop.stg_orders",
                "name": "stg_orders",
                "description": "Staged orders from raw source",
                "schema": "staging",
                "database": "analytics",
                "materialization": "view",
                "tags": ["staging", "orders"],
                "meta": {},
                "path": "models/staging/stg_orders.sql",
                "folder": "models/staging",
                "raw_sql": "SELECT * FROM {{ source('jaffle_shop', 'raw_orders') }}",
                "compiled_sql": "SELECT * FROM raw.jaffle_shop.raw_orders",
                "columns": [
                    {
                        "name": "order_id",
                        "description": "Primary key",
                        "data_type": "INTEGER",
                        "meta": {},
                        "tags": [],
                        "tests": [
                            {
                                "test_name": "unique_stg_orders_order_id",
                                "test_type": "unique",
                                "status": "pass",
                            }
                        ],
                    },
                    {
                        "name": "customer_id",
                        "description": "",
                        "data_type": "INTEGER",
                        "meta": {},
                        "tags": [],
                        "tests": [],
                    },
                    {
                        "name": "status",
                        "description": "Order status",
                        "data_type": "VARCHAR",
                        "meta": {},
                        "tags": [],
                        "tests": [],
                    },
                ],
                "depends_on": ["source.jaffle_shop.jaffle_shop.raw_orders"],
                "referenced_by": ["model.jaffle_shop.fct_orders"],
                "sources_used": ["source.jaffle_shop.jaffle_shop.raw_orders"],
                "test_results": [
                    {
                        "test_name": "unique_stg_orders_order_id",
                        "test_type": "unique",
                        "column_name": "order_id",
                        "status": "pass",
                        "execution_time": 0.1,
                        "failures": 0,
                        "message": None,
                    }
                ],
                "last_run": {
                    "status": "success",
                    "execution_time": 0.5,
                    "completed_at": "2025-01-01T00:00:00Z",
                },
                "catalog_stats": {"row_count": 100, "bytes": None, "has_stats": True},
                "is_package": False,
            },
            "model.jaffle_shop.fct_orders": {
                "unique_id": "model.jaffle_shop.fct_orders",
                "name": "fct_orders",
                "description": "",
                "schema": "marts",
                "database": "analytics",
                "materialization": "table",
                "tags": ["marts"],
                "meta": {},
                "path": "models/marts/fct_orders.sql",
                "folder": "models/marts",
                "raw_sql": "SELECT * FROM {{ ref('stg_orders') }}",
                "compiled_sql": "SELECT * FROM analytics.staging.stg_orders",
                "columns": [
                    {
                        "name": "order_id",
                        "description": "",
                        "data_type": "INTEGER",
                        "meta": {},
                        "tags": [],
                        "tests": [],
                    },
                ],
                "depends_on": ["model.jaffle_shop.stg_orders"],
                "referenced_by": [],
                "sources_used": [],
                "test_results": [],
                "last_run": None,
                "catalog_stats": {"row_count": None, "bytes": None, "has_stats": False},
                "is_package": False,
            },
            "model.dbt_utils.surrogate_key": {
                "unique_id": "model.dbt_utils.surrogate_key",
                "name": "surrogate_key",
                "description": "Package model",
                "schema": "public",
                "database": "analytics",
                "materialization": "view",
                "tags": [],
                "meta": {},
                "path": "models/utils/surrogate_key.sql",
                "folder": "models/utils",
                "raw_sql": "",
                "compiled_sql": "",
                "columns": [],
                "depends_on": [],
                "referenced_by": [],
                "sources_used": [],
                "test_results": [],
                "last_run": None,
                "catalog_stats": {"row_count": None, "bytes": None, "has_stats": False},
                "is_package": True,
            },
        },
        "sources": {
            "source.jaffle_shop.jaffle_shop.raw_orders": {
                "unique_id": "source.jaffle_shop.jaffle_shop.raw_orders",
                "name": "raw_orders",
                "source_name": "jaffle_shop",
                "description": "Raw orders table",
                "schema": "raw",
                "database": "analytics",
                "columns": [
                    {"name": "order_id", "description": "PK", "data_type": "INTEGER"},
                    {"name": "customer_id", "description": "", "data_type": "INTEGER"},
                ],
                "tags": [],
                "meta": {},
                "loader": "fivetran",
                "loaded_at_field": "updated_at",
                "freshness_status": "pass",
                "freshness_max_loaded_at": "2025-01-01",
                "freshness_snapshotted_at": "2025-01-01",
            },
        },
        "seeds": {},
        "snapshots": {},
        "exposures": {},
        "metrics": {},
        "health": {
            "score": {
                "overall": 72.5,
                "documentation": 60.0,
                "testing": 40.0,
                "freshness": 100.0,
                "complexity": 90.0,
                "naming": 80.0,
                "orphans": 85.0,
                "grade": "C",
            },
            "coverage": {},
            "complexity": {},
            "naming": {},
            "orphans": [],
        },
        "search_index": [],
        "lineage": {"nodes": [], "edges": []},
    }


class TestListModels:
    def test_lists_all_non_package_models(self, sample_data: dict) -> None:
        result = TOOL_MAP["list_models"].handler(sample_data, {})
        assert result["count"] == 2
        names = {m["name"] for m in result["models"]}
        assert names == {"stg_orders", "fct_orders"}

    def test_includes_packages_when_requested(self, sample_data: dict) -> None:
        result = TOOL_MAP["list_models"].handler(sample_data, {"include_packages": True})
        assert result["count"] == 3

    def test_filters_by_name_pattern(self, sample_data: dict) -> None:
        result = TOOL_MAP["list_models"].handler(sample_data, {"name_pattern": "stg_*"})
        assert result["count"] == 1
        assert result["models"][0]["name"] == "stg_orders"

    def test_filters_by_folder(self, sample_data: dict) -> None:
        result = TOOL_MAP["list_models"].handler(sample_data, {"folder": "models/marts"})
        assert result["count"] == 1
        assert result["models"][0]["name"] == "fct_orders"

    def test_filters_by_tag(self, sample_data: dict) -> None:
        result = TOOL_MAP["list_models"].handler(sample_data, {"tag": "staging"})
        assert result["count"] == 1


class TestGetModel:
    def test_get_by_name(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_model"].handler(sample_data, {"name": "stg_orders"})
        assert result["name"] == "stg_orders"
        assert result["description"] == "Staged orders from raw source"
        assert len(result["columns"]) == 3

    def test_get_by_unique_id(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_model"].handler(
            sample_data, {"unique_id": "model.jaffle_shop.stg_orders"}
        )
        assert result["name"] == "stg_orders"

    def test_not_found(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_model"].handler(sample_data, {"name": "nonexistent"})
        assert "error" in result


class TestGetSource:
    def test_get_by_name(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_source"].handler(sample_data, {"name": "raw_orders"})
        assert result["name"] == "raw_orders"
        assert result["freshness_status"] == "pass"

    def test_get_by_qualified_name(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_source"].handler(sample_data, {"name": "jaffle_shop.raw_orders"})
        assert result["name"] == "raw_orders"

    def test_not_found(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_source"].handler(sample_data, {"name": "nope"})
        assert "error" in result


class TestGetLineage:
    def test_upstream(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_lineage"].handler(
            sample_data, {"name": "fct_orders", "direction": "upstream"}
        )
        assert result["target"] == "model.jaffle_shop.fct_orders"
        upstream_ids = [u["unique_id"] for u in result["upstream"]]
        assert "model.jaffle_shop.stg_orders" in upstream_ids

    def test_downstream(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_lineage"].handler(
            sample_data, {"name": "stg_orders", "direction": "downstream"}
        )
        downstream_ids = [d["unique_id"] for d in result["downstream"]]
        assert "model.jaffle_shop.fct_orders" in downstream_ids

    def test_both_directions(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_lineage"].handler(
            sample_data, {"name": "stg_orders", "direction": "both"}
        )
        assert len(result["upstream"]) > 0
        assert len(result["downstream"]) > 0

    def test_not_found(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_lineage"].handler(sample_data, {"name": "nope"})
        assert "error" in result


class TestGetHealth:
    def test_returns_health_data(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_health"].handler(sample_data, {})
        assert result["score"]["overall"] == 72.5
        assert result["score"]["grade"] == "C"


class TestFindUndocumented:
    def test_finds_undocumented_models(self, sample_data: dict) -> None:
        result = TOOL_MAP["find_undocumented"].handler(sample_data, {"resource_type": "model"})
        assert result["total_undocumented_models"] == 1
        assert result["undocumented_models"][0]["name"] == "fct_orders"

    def test_finds_undocumented_columns(self, sample_data: dict) -> None:
        result = TOOL_MAP["find_undocumented"].handler(sample_data, {"resource_type": "column"})
        assert result["total_undocumented_columns"] > 0

    def test_sorted_by_downstream_impact(self, sample_data: dict) -> None:
        result = TOOL_MAP["find_undocumented"].handler(sample_data, {"resource_type": "both"})
        # stg_orders columns should rank higher (has 1 downstream)
        cols = result["undocumented_columns"]
        if len(cols) >= 2:
            assert cols[0]["downstream_count"] >= cols[-1]["downstream_count"]


class TestFindUntested:
    def test_finds_untested_models(self, sample_data: dict) -> None:
        result = TOOL_MAP["find_untested"].handler(sample_data, {})
        assert result["total_untested_models"] == 1
        assert result["untested_models"][0]["name"] == "fct_orders"

    def test_finds_untested_columns(self, sample_data: dict) -> None:
        result = TOOL_MAP["find_untested"].handler(sample_data, {})
        # customer_id and status in stg_orders have no tests
        untested_col_names = {c["column"] for c in result["untested_columns"]}
        assert "customer_id" in untested_col_names


class TestSearch:
    def test_exact_name_match(self, sample_data: dict) -> None:
        result = TOOL_MAP["search"].handler(sample_data, {"query": "stg_orders"})
        assert result["results"][0]["name"] == "stg_orders"
        assert result["results"][0]["score"] == 100

    def test_partial_name_match(self, sample_data: dict) -> None:
        result = TOOL_MAP["search"].handler(sample_data, {"query": "orders"})
        assert len(result["results"]) >= 2

    def test_description_match(self, sample_data: dict) -> None:
        result = TOOL_MAP["search"].handler(sample_data, {"query": "staged"})
        assert any(r["name"] == "stg_orders" for r in result["results"])

    def test_tag_match(self, sample_data: dict) -> None:
        result = TOOL_MAP["search"].handler(sample_data, {"query": "marts"})
        assert any(r["name"] == "fct_orders" for r in result["results"])

    def test_empty_query(self, sample_data: dict) -> None:
        result = TOOL_MAP["search"].handler(sample_data, {"query": ""})
        assert "error" in result

    def test_limit(self, sample_data: dict) -> None:
        result = TOOL_MAP["search"].handler(sample_data, {"query": "orders", "limit": 1})
        assert len(result["results"]) == 1


class TestGetColumnInfo:
    def test_finds_column_across_models(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_column_info"].handler(sample_data, {"column_name": "order_id"})
        assert result["count"] >= 2  # stg_orders + fct_orders
        model_names = {o.get("model_name") for o in result["occurrences"]}
        assert "stg_orders" in model_names

    def test_case_insensitive(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_column_info"].handler(sample_data, {"column_name": "ORDER_ID"})
        assert result["count"] >= 2

    def test_includes_sources(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_column_info"].handler(sample_data, {"column_name": "order_id"})
        source_names = {o.get("source_name") for o in result["occurrences"] if "source_name" in o}
        assert "jaffle_shop.raw_orders" in source_names

    def test_empty_column_name(self, sample_data: dict) -> None:
        result = TOOL_MAP["get_column_info"].handler(sample_data, {"column_name": ""})
        assert "error" in result


class TestToolRegistry:
    def test_all_tools_registered(self) -> None:
        assert len(TOOLS) == 9

    def test_tool_map_matches_list(self) -> None:
        assert set(TOOL_MAP.keys()) == {t.name for t in TOOLS}

    def test_all_tools_have_schemas(self) -> None:
        for tool in TOOLS:
            assert "type" in tool.input_schema
            assert tool.input_schema["type"] == "object"
