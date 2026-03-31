"""Tests for column lineage analyzer — caching behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from docglow.lineage.analyzer import (
    _hash_sql,
    _load_cache,
    _save_cache,
    compute_column_lineage_subset,
)


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def cache_file(cache_dir: Path) -> Path:
    return cache_dir / "test-cache.json"


class TestHashSql:
    def test_deterministic(self) -> None:
        assert _hash_sql("SELECT 1") == _hash_sql("SELECT 1")

    def test_different_sql_different_hash(self) -> None:
        assert _hash_sql("SELECT 1") != _hash_sql("SELECT 2")

    def test_returns_16_char_hex(self) -> None:
        h = _hash_sql("SELECT 1")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestCacheRoundTrip:
    def test_save_and_load(self, cache_file: Path) -> None:
        cache: dict[str, Any] = {
            "model.test.foo": {
                "sql_hash": "abc123",
                "lineage": {
                    "col_a": [
                        {
                            "source_model": "x",
                            "source_column": "y",
                            "transformation": "passthrough",
                        }
                    ]
                },
            },
        }
        _save_cache(cache_file, cache, "postgres")
        loaded = _load_cache(cache_file, "postgres")
        assert loaded["model.test.foo"]["sql_hash"] == "abc123"
        assert len(loaded["model.test.foo"]["lineage"]["col_a"]) == 1

    def test_load_missing_file(self, cache_dir: Path) -> None:
        result = _load_cache(cache_dir / "nonexistent.json", "postgres")
        assert result == {}

    def test_load_none_path(self) -> None:
        result = _load_cache(None, "postgres")
        assert result == {}

    def test_save_none_path(self) -> None:
        # Should not raise
        _save_cache(None, {"foo": "bar"}, "postgres")

    def test_invalid_json(self, cache_file: Path) -> None:
        cache_file.write_text("not json", encoding="utf-8")
        result = _load_cache(cache_file, "postgres")
        assert result == {}


class TestCacheInvalidation:
    def test_version_change_invalidates(self, cache_file: Path) -> None:
        cache: dict[str, Any] = {"model.test.foo": {"sql_hash": "abc", "lineage": {}}}
        _save_cache(cache_file, cache, "postgres")

        # Patch version to simulate upgrade
        with patch("docglow.lineage.analyzer.__version__", "99.99.99"):
            loaded = _load_cache(cache_file, "postgres")
        assert loaded == {}

    def test_dialect_change_invalidates(self, cache_file: Path) -> None:
        cache: dict[str, Any] = {"model.test.foo": {"sql_hash": "abc", "lineage": {}}}
        _save_cache(cache_file, cache, "postgres")

        loaded = _load_cache(cache_file, "snowflake")
        assert loaded == {}

    def test_direct_migrated_to_passthrough(self, cache_file: Path) -> None:
        """Old caches with 'direct' should be migrated to 'passthrough' on load."""
        cache: dict[str, Any] = {
            "model.test.bar": {
                "sql_hash": "def456",
                "lineage": {
                    "col_x": [
                        {
                            "source_model": "a",
                            "source_column": "b",
                            "transformation": "direct",
                        }
                    ],
                    "col_y": [
                        {
                            "source_model": "a",
                            "source_column": "c",
                            "transformation": "aggregated",
                        }
                    ],
                },
            },
        }
        _save_cache(cache_file, cache, "postgres")
        loaded = _load_cache(cache_file, "postgres")
        deps_x = loaded["model.test.bar"]["lineage"]["col_x"]
        deps_y = loaded["model.test.bar"]["lineage"]["col_y"]
        assert deps_x[0]["transformation"] == "passthrough"
        assert deps_y[0]["transformation"] == "aggregated"

    def test_same_version_and_dialect_preserves(self, cache_file: Path) -> None:
        cache: dict[str, Any] = {"model.test.foo": {"sql_hash": "abc", "lineage": {}}}
        _save_cache(cache_file, cache, "duckdb")

        loaded = _load_cache(cache_file, "duckdb")
        assert "model.test.foo" in loaded


# --- Subset computation tests ---


@pytest.fixture()
def dag_models() -> dict[str, dict[str, Any]]:
    """A small DAG: source -> stg_orders -> fct_orders -> dim_summary."""
    return {
        "model.proj.stg_orders": {
            "name": "stg_orders",
            "folder": "models/staging",
            "path": "models/staging/stg_orders.sql",
            "depends_on": ["source.proj.raw.orders"],
            "referenced_by": ["model.proj.fct_orders"],
        },
        "model.proj.fct_orders": {
            "name": "fct_orders",
            "folder": "models/marts",
            "path": "models/marts/fct_orders.sql",
            "depends_on": ["model.proj.stg_orders", "model.proj.stg_customers"],
            "referenced_by": ["model.proj.dim_summary"],
        },
        "model.proj.stg_customers": {
            "name": "stg_customers",
            "folder": "models/staging",
            "path": "models/staging/stg_customers.sql",
            "depends_on": ["source.proj.raw.customers"],
            "referenced_by": ["model.proj.fct_orders"],
        },
        "model.proj.dim_summary": {
            "name": "dim_summary",
            "folder": "models/marts",
            "path": "models/marts/dim_summary.sql",
            "depends_on": ["model.proj.fct_orders"],
            "referenced_by": [],
        },
    }


@pytest.fixture()
def dag_sources() -> dict[str, dict[str, Any]]:
    return {
        "source.proj.raw.orders": {
            "name": "orders",
            "source_name": "raw",
            "depends_on": [],
            "referenced_by": ["model.proj.stg_orders"],
        },
        "source.proj.raw.customers": {
            "name": "customers",
            "source_name": "raw",
            "depends_on": [],
            "referenced_by": ["model.proj.stg_customers"],
        },
    }


class TestComputeColumnLineageSubset:
    def test_upstream_default(self, dag_models: dict, dag_sources: dict) -> None:
        """No + operator = upstream only."""
        result = compute_column_lineage_subset("fct_orders", dag_models, dag_sources, {}, {})
        assert "model.proj.fct_orders" in result
        assert "model.proj.stg_orders" in result
        assert "model.proj.stg_customers" in result
        assert "source.proj.raw.orders" in result
        # dim_summary is downstream, should NOT be included
        assert "model.proj.dim_summary" not in result

    def test_upstream_explicit(self, dag_models: dict, dag_sources: dict) -> None:
        """+fct_orders = explicit upstream."""
        result = compute_column_lineage_subset("+fct_orders", dag_models, dag_sources, {}, {})
        assert "model.proj.fct_orders" in result
        assert "model.proj.stg_orders" in result
        assert "model.proj.dim_summary" not in result

    def test_downstream_only(self, dag_models: dict, dag_sources: dict) -> None:
        """fct_orders+ = downstream only."""
        result = compute_column_lineage_subset("fct_orders+", dag_models, dag_sources, {}, {})
        assert "model.proj.fct_orders" in result
        assert "model.proj.dim_summary" in result
        # Upstream should NOT be included
        assert "model.proj.stg_orders" not in result

    def test_both_directions(self, dag_models: dict, dag_sources: dict) -> None:
        """+fct_orders+ = both directions."""
        result = compute_column_lineage_subset("+fct_orders+", dag_models, dag_sources, {}, {})
        assert "model.proj.fct_orders" in result
        assert "model.proj.stg_orders" in result
        assert "model.proj.dim_summary" in result

    def test_depth_limit_1(self, dag_models: dict, dag_sources: dict) -> None:
        """Depth=1 returns only direct parents."""
        result = compute_column_lineage_subset(
            "fct_orders", dag_models, dag_sources, {}, {}, max_depth=1
        )
        assert "model.proj.fct_orders" in result
        assert "model.proj.stg_orders" in result
        assert "model.proj.stg_customers" in result
        # Sources are 2 hops away, should NOT be included
        assert "source.proj.raw.orders" not in result

    def test_depth_limit_0(self, dag_models: dict, dag_sources: dict) -> None:
        """Depth=0 returns only the seed model itself."""
        result = compute_column_lineage_subset(
            "fct_orders", dag_models, dag_sources, {}, {}, max_depth=0
        )
        assert result == {"model.proj.fct_orders"}

    def test_glob_pattern(self, dag_models: dict, dag_sources: dict) -> None:
        """Glob patterns match multiple models."""
        result = compute_column_lineage_subset("stg_*", dag_models, dag_sources, {}, {})
        assert "model.proj.stg_orders" in result
        assert "model.proj.stg_customers" in result
        # Their upstream sources should be included
        assert "source.proj.raw.orders" in result
        assert "source.proj.raw.customers" in result

    def test_no_match_returns_empty(self, dag_models: dict, dag_sources: dict) -> None:
        result = compute_column_lineage_subset("nonexistent_model", dag_models, dag_sources, {}, {})
        assert result == set()

    def test_sources_in_depends_on_included(self, dag_models: dict, dag_sources: dict) -> None:
        """Sources referenced in depends_on are included in the subset."""
        result = compute_column_lineage_subset("stg_orders", dag_models, dag_sources, {}, {})
        assert "source.proj.raw.orders" in result
