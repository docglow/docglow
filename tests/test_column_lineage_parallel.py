"""Tests for parallel column lineage analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docglow.artifacts.loader import load_artifacts
from docglow.lineage.analyzer import (
    _analyze_single_model,
    _compute_depth_waves,
    _ModelLineageResult,
    analyze_column_lineage,
)
from docglow.lineage.column_parser import build_schema_mapping, detect_dialect
from docglow.lineage.table_resolver import TableResolver

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_test_data() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], Any, str | None
]:
    """Load jaffle-shop test fixtures and return transformed model dicts."""
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


class TestComputeDepthWaves:
    """Test topological wave computation."""

    def test_linear_chain(self) -> None:
        """A -> B -> C should produce 3 waves."""
        models = {
            "a": {"depends_on": []},
            "b": {"depends_on": ["a"]},
            "c": {"depends_on": ["b"]},
        }
        waves = _compute_depth_waves(models)
        assert len(waves) == 3
        assert set(waves[0]) == {"a"}
        assert set(waves[1]) == {"b"}
        assert set(waves[2]) == {"c"}

    def test_diamond(self) -> None:
        """Diamond: A -> B, A -> C, B -> D, C -> D."""
        models = {
            "a": {"depends_on": []},
            "b": {"depends_on": ["a"]},
            "c": {"depends_on": ["a"]},
            "d": {"depends_on": ["b", "c"]},
        }
        waves = _compute_depth_waves(models)
        assert len(waves) == 3
        assert set(waves[0]) == {"a"}
        assert set(waves[1]) == {"b", "c"}
        assert set(waves[2]) == {"d"}

    def test_wide_independent(self) -> None:
        """All independent models should be in one wave."""
        models = {
            "a": {"depends_on": []},
            "b": {"depends_on": []},
            "c": {"depends_on": []},
        }
        waves = _compute_depth_waves(models)
        assert len(waves) == 1
        assert set(waves[0]) == {"a", "b", "c"}

    def test_external_deps_ignored(self) -> None:
        """Dependencies on sources (outside model set) don't block."""
        models = {
            "a": {"depends_on": ["source.external"]},
            "b": {"depends_on": ["source.other"]},
        }
        waves = _compute_depth_waves(models)
        assert len(waves) == 1
        assert set(waves[0]) == {"a", "b"}

    def test_empty(self) -> None:
        waves = _compute_depth_waves({})
        assert waves == []


class TestAnalyzeSingleModel:
    """Test the pure per-model analysis function."""

    def test_returns_result_for_valid_sql(self) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_test_data()
        schema = build_schema_mapping(models, sources)
        resolver = TableResolver(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )

        # Pick a model that has SQL
        uid = next(uid for uid, m in models.items() if m.get("compiled_sql"))
        result = _analyze_single_model(uid, models[uid], schema, resolver, dialect, None)

        assert isinstance(result, _ModelLineageResult)
        assert result.uid == uid
        assert not result.skipped
        assert not result.cached

    def test_skips_model_without_sql(self) -> None:
        schema: dict[str, dict[str, str]] = {}
        resolver = TableResolver(models={}, sources={}, seeds={}, snapshots={})
        result = _analyze_single_model(
            "test.empty",
            {"name": "empty"},
            schema,
            resolver,
            None,
            None,
        )
        assert result.skipped

    def test_returns_cache_hit(self) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_test_data()
        schema = build_schema_mapping(models, sources)
        resolver = TableResolver(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )

        uid = next(uid for uid, m in models.items() if m.get("compiled_sql"))

        # First call to get the cache entry
        first = _analyze_single_model(uid, models[uid], schema, resolver, dialect, None)

        # Second call with cached entry
        second = _analyze_single_model(
            uid,
            models[uid],
            schema,
            resolver,
            dialect,
            first.cache_entry,
        )
        assert second.cached
        assert second.lineage == first.lineage


class TestParallelVsSequential:
    """Verify parallel and sequential produce identical results."""

    def test_results_match(self) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_test_data()

        common_kwargs = dict(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
        )

        sequential = analyze_column_lineage(**common_kwargs, max_workers=1)
        parallel = analyze_column_lineage(**common_kwargs, max_workers=4)

        assert sequential.keys() == parallel.keys()
        for uid in sequential:
            assert sequential[uid].keys() == parallel[uid].keys(), f"Column mismatch for {uid}"
            for col in sequential[uid]:
                seq_deps = sorted(str(d) for d in sequential[uid][col])
                par_deps = sorted(str(d) for d in parallel[uid][col])
                assert seq_deps == par_deps, f"Dep mismatch {uid}.{col}"

    def test_cache_valid_after_parallel(self, tmp_path: Path) -> None:
        models, sources, seeds, snapshots, manifest, dialect = _load_test_data()
        cache_path = tmp_path / ".cache.json"

        analyze_column_lineage(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
            cache_path=cache_path,
            max_workers=4,
        )

        assert cache_path.exists()
        cache = json.loads(cache_path.read_text())
        assert "__cache_meta__" in cache
        assert len(cache) > 1  # meta + at least one model
