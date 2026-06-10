"""Tests for column lineage analyzer — caching behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from docglow.lineage.analyzer import (
    _hash_sql,
    _load_cache,
    _ModelLineageResult,
    _save_cache,
    analyze_column_lineage,
    analyze_one_model,
    compute_column_lineage_subset,
    deserialize_shared_state,
    serialize_shared_state,
)
from docglow.lineage.column_parser import detect_dialect
from docglow.lineage.table_resolver import TableResolver

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_jaffle_shop_data() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], Any, str | None
]:
    """Load jaffle-shop fixtures, returning transformed model dicts + manifest + dialect.

    Mirrors the loader used by tests/test_column_lineage_parallel.py so the U1
    per-model path is exercised against the same fixtures as the whole-project path.
    """
    from docglow.artifacts.loader import load_artifacts
    from docglow.generator.pipeline import (
        PipelineContext,
        stage_filter_nodes,
        stage_transform_nodes,
        stage_transform_sources,
    )

    project = FIXTURES_DIR.parent.parent / "examples" / "jaffle-shop"
    artifacts = load_artifacts(project)
    ctx = PipelineContext(artifacts=artifacts, column_lineage_enabled=True)
    stage_transform_nodes(ctx)
    stage_filter_nodes(ctx)
    stage_transform_sources(ctx)
    dialect = detect_dialect(artifacts.manifest.metadata.adapter_type)
    return ctx.models, ctx.sources, ctx.seeds, ctx.snapshots, artifacts.manifest, dialect


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


# --- U1: per-model entrypoint + shared-state serialization ---


def _inline_resolver(
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
    manifest: Any,
) -> TableResolver:
    """Build a TableResolver the same way analyze_column_lineage does."""
    return TableResolver(
        models=models,
        sources=sources,
        seeds=seeds,
        snapshots=snapshots,
        manifest_nodes=dict(manifest.nodes),
        manifest_sources=dict(manifest.sources),
    )


class TestSerializeSharedStateRoundTrip:
    """serialize -> deserialize must reproduce an identically-resolving resolver."""

    def test_resolver_round_trip_resolves_identically(self) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_jaffle_shop_data()
        inline = _inline_resolver(models, sources, seeds, snapshots, manifest)

        blob = serialize_shared_state(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )
        resolver, schema, out_dialect = deserialize_shared_state(blob)

        assert out_dialect == dialect

        # Resolve every short ref the inline resolver knows about — identical results.
        refs_to_check = list(inline._short.keys()) + list(inline._lower.keys())
        assert refs_to_check, "expected jaffle-shop to populate resolver lookups"
        for ref in refs_to_check:
            assert resolver.resolve(ref) == inline.resolve(ref)

    def test_blob_is_json_serializable(self) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_jaffle_shop_data()
        blob = serialize_shared_state(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )
        import json

        # Round-trips through JSON unchanged (state is only string dicts).
        assert json.loads(json.dumps(blob)) == blob
        assert set(blob.keys()) == {"resolver", "schema", "dialect"}
        assert set(blob["resolver"].keys()) == {"exact", "lower", "short"}

    def test_table_resolver_to_from_dict_unit(self) -> None:
        models = {"model.proj.users": {"name": "users", "schema": "public", "database": "mydb"}}
        original = TableResolver(models=models, sources={})
        rebuilt = TableResolver.from_dict(original.to_dict())
        for ref in ("public.users", "mydb.public.users", "PUBLIC.USERS", "nope.table"):
            assert rebuilt.resolve(ref) == original.resolve(ref)


class TestAnalyzeOneModel:
    """The public per-model entrypoint."""

    def test_happy_path_matches_expected_dependencies(self) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_jaffle_shop_data()
        blob = serialize_shared_state(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )
        shared = deserialize_shared_state(blob)

        # Pick a model that produces resolved lineage in the project-wide path.
        project = analyze_column_lineage(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )
        uid = next(u for u, frag in project.items() if frag)

        result = analyze_one_model(uid, models[uid], shared)
        assert isinstance(result, _ModelLineageResult)
        assert result.uid == uid
        assert result.lineage  # non-empty fragment
        # Each dependency carries the resolved triple.
        for deps in result.lineage.values():
            for dep in deps:
                assert set(dep.keys()) >= {
                    "source_model",
                    "source_column",
                    "transformation",
                }

    def test_parity_with_project_wide_path(self) -> None:
        """analyze_one_model produces identical lineage to analyze_column_lineage."""
        models, sources, seeds, snapshots, manifest, dialect = _load_jaffle_shop_data()
        blob = serialize_shared_state(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )
        shared = deserialize_shared_state(blob)

        project = analyze_column_lineage(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
            max_workers=1,
        )

        # Compare the fragment for every model that the project path produced.
        all_models = {**models, **seeds, **snapshots}
        checked = 0
        for uid, expected_fragment in project.items():
            result = analyze_one_model(uid, all_models[uid], shared)
            assert result.lineage == expected_fragment, f"fragment mismatch for {uid}"
            checked += 1
        assert checked > 0, "expected at least one model with lineage to compare"

    def test_select_star_with_schema_expands(self) -> None:
        """SELECT * with schema present expands to the upstream columns."""
        models = {
            "model.proj.stg": {
                "name": "stg",
                "schema": "public",
                "database": "db",
                "compiled_sql": "SELECT id, email FROM db.public.raw_users",
                "columns": [{"name": "id"}, {"name": "email"}],
            },
            "model.proj.dwn": {
                "name": "dwn",
                "schema": "public",
                "database": "db",
                "compiled_sql": "SELECT * FROM db.public.stg",
                "columns": [{"name": "id"}, {"name": "email"}],
            },
        }
        sources = {
            "source.proj.raw.raw_users": {
                "name": "raw_users",
                "source_name": "raw",
                "schema": "public",
                "database": "db",
                "columns": [{"name": "id"}, {"name": "email"}],
            }
        }
        blob = serialize_shared_state(
            models=models, sources=sources, seeds={}, snapshots={}, dialect="postgres"
        )
        shared = deserialize_shared_state(blob)

        result = analyze_one_model("model.proj.dwn", models["model.proj.dwn"], shared)
        # SELECT * expanded against the schema → both columns traced to stg.
        assert set(result.lineage.keys()) == {"id", "email"}
        for col, deps in result.lineage.items():
            assert deps[0]["source_model"] == "model.proj.stg"

    def test_select_star_empty_schema_no_crash(self) -> None:
        """SELECT * with empty schema falls back leniently — no crash."""
        models = {
            "model.proj.dwn": {
                "name": "dwn",
                "schema": "public",
                "database": "db",
                "compiled_sql": "SELECT * FROM db.public.stg",
                "columns": [{"name": "id"}],
            }
        }
        # Empty schema mapping → SELECT * cannot expand.
        shared = (TableResolver(models=models, sources={}), {}, "postgres")
        result = analyze_one_model("model.proj.dwn", models["model.proj.dwn"], shared)
        assert isinstance(result, _ModelLineageResult)
        # No exception; fragment may be empty since columns can't be expanded.

    def test_no_edges_returns_empty_fragment(self) -> None:
        """A model whose deps trace to nothing returns an empty .lineage, not a raise."""
        models = {
            "model.proj.lit": {
                "name": "lit",
                "schema": "public",
                "database": "db",
                # Literal columns reference no upstream table → nothing resolvable.
                "compiled_sql": "SELECT 1 AS a, 'x' AS b",
                "columns": [{"name": "a"}, {"name": "b"}],
            }
        }
        blob = serialize_shared_state(
            models=models, sources={}, seeds={}, snapshots={}, dialect="postgres"
        )
        shared = deserialize_shared_state(blob)
        result = analyze_one_model("model.proj.lit", models["model.proj.lit"], shared)
        assert result.lineage == {}

    def test_malformed_sql_returns_structured_failure(self) -> None:
        """Unparseable SQL → structured per-model failure, never a raised exception."""
        models = {
            "model.proj.broken": {
                "name": "broken",
                "schema": "public",
                "database": "db",
                "compiled_sql": "SELECT FROM WHERE ((( not valid sql at all",
                "columns": [{"name": "x"}],
            }
        }
        blob = serialize_shared_state(
            models=models, sources={}, seeds={}, snapshots={}, dialect="postgres"
        )
        shared = deserialize_shared_state(blob)
        # Must not raise.
        result = analyze_one_model("model.proj.broken", models["model.proj.broken"], shared)
        assert isinstance(result, _ModelLineageResult)
        assert result.failure is not None
        assert result.failure["model"] == "model.proj.broken"
        assert result.lineage == {}

    def test_skips_model_without_sql(self) -> None:
        shared = (TableResolver(models={}, sources={}), {}, None)
        result = analyze_one_model("model.proj.empty", {"name": "empty"}, shared)
        assert result.skipped
