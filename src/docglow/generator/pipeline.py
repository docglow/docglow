"""Generation pipeline — discrete, named stages for building DocglowData."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from docglow import __version__
from docglow.artifacts.loader import LoadedArtifacts
from docglow.generator.layers import LineageLayerConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Mutable context passed through each pipeline stage.

    Each stage reads what it needs and writes its output here.
    The final result is assembled from this context.
    """

    # Inputs
    artifacts: LoadedArtifacts
    profiling_enabled: bool = False
    ai_enabled: bool = False
    ai_key: str | None = None
    select: str | None = None
    exclude: str | None = None
    layer_config: LineageLayerConfig = field(default_factory=LineageLayerConfig)
    column_lineage_enabled: bool = False
    column_lineage_select: str | None = None
    column_lineage_depth: int | None = None
    column_lineage_cache_dir: Any | None = None
    exclude_packages: bool = True
    slim: bool = False

    # Lookup maps (populated by build_lookups stage)
    run_results_by_id: dict[str, Any] = field(default_factory=dict)
    test_nodes_by_model: dict[str, list[Any]] = field(default_factory=dict)
    reverse_deps: dict[str, list[str]] = field(default_factory=dict)
    root_project_name: str = ""

    # Transformed data (populated by transform stages)
    models: dict[str, Any] = field(default_factory=dict)
    seeds: dict[str, Any] = field(default_factory=dict)
    snapshots: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Any] = field(default_factory=dict)
    exposures: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    # Derived data (populated by analysis stages)
    lineage: dict[str, Any] = field(default_factory=dict)
    search_index: list[dict[str, Any]] = field(default_factory=list)
    health: dict[str, Any] = field(default_factory=dict)
    column_lineage: dict[str, Any] | None = None
    ai_context: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineStage:
    """A named stage in the generation pipeline."""

    name: str
    fn: Any  # Callable[[PipelineContext], None]
    enabled: bool = True


def run_pipeline(stages: list[PipelineStage], ctx: PipelineContext) -> None:
    """Execute pipeline stages in order, logging timing for each."""
    for stage in stages:
        if not stage.enabled:
            logger.debug("Skipping stage: %s (disabled)", stage.name)
            continue
        start = time.monotonic()
        stage.fn(ctx)
        elapsed = time.monotonic() - start
        logger.debug("Stage '%s' completed in %.2fs", stage.name, elapsed)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def stage_build_lookups(ctx: PipelineContext) -> None:
    """Build lookup maps from artifacts for efficient cross-referencing."""
    from docglow.generator.transforms.lookups import (
        build_reverse_dependency_map,
        build_run_results_map,
        build_test_map,
    )

    ctx.root_project_name = ctx.artifacts.manifest.metadata.project_name or ""
    ctx.run_results_by_id = build_run_results_map(ctx.artifacts.run_results)
    ctx.test_nodes_by_model = build_test_map(ctx.artifacts.manifest)
    ctx.reverse_deps = build_reverse_dependency_map(ctx.artifacts.manifest)


def stage_transform_nodes(ctx: PipelineContext) -> None:
    """Transform manifest nodes into Docglow model/seed/snapshot dicts."""
    from docglow.generator.transforms.models import transform_model

    manifest = ctx.artifacts.manifest
    catalog = ctx.artifacts.catalog

    for unique_id, node in manifest.nodes.items():
        if node.resource_type not in ("model", "seed", "snapshot"):
            continue

        is_package = bool(ctx.root_project_name and node.package_name != ctx.root_project_name)
        data = transform_model(
            node, catalog, ctx.run_results_by_id, ctx.test_nodes_by_model, ctx.reverse_deps
        )
        data["is_package"] = is_package

        if node.resource_type == "model":
            ctx.models[unique_id] = data
        elif node.resource_type == "seed":
            ctx.seeds[unique_id] = data
        else:
            ctx.snapshots[unique_id] = data


def stage_filter_nodes(ctx: PipelineContext) -> None:
    """Apply --select / --exclude filtering to models, seeds, snapshots."""
    if not ctx.select and not ctx.exclude:
        return

    from docglow.generator.filters import filter_resources

    ctx.models, ctx.seeds, ctx.snapshots = filter_resources(
        ctx.models, ctx.seeds, ctx.snapshots, select=ctx.select, exclude=ctx.exclude
    )


def stage_transform_sources(ctx: PipelineContext) -> None:
    """Transform manifest sources into Docglow source dicts."""
    from docglow.generator.transforms.sources import transform_source

    manifest = ctx.artifacts.manifest
    catalog = ctx.artifacts.catalog

    for unique_id, source in manifest.sources.items():
        ctx.sources[unique_id] = transform_source(source, catalog, ctx.artifacts.source_freshness)


def stage_transform_exposures_metrics(ctx: PipelineContext) -> None:
    """Transform exposures and metrics."""
    manifest = ctx.artifacts.manifest

    for unique_id, exposure in manifest.exposures.items():
        ctx.exposures[unique_id] = {
            "unique_id": unique_id,
            "name": exposure.name,
            "type": exposure.type,
            "description": exposure.description,
            "depends_on": exposure.depends_on.nodes,
            "owner": dict(exposure.owner),
            "tags": list(exposure.tags),
        }

    for unique_id, metric in manifest.metrics.items():
        ctx.metrics[unique_id] = {
            "unique_id": unique_id,
            "name": metric.name,
            "description": metric.description,
            "label": metric.label,
            "type": metric.type,
            "depends_on": metric.depends_on.nodes,
            "tags": list(metric.tags),
        }


def stage_build_lineage(ctx: PipelineContext) -> None:
    """Build the lineage graph."""
    from docglow.generator.lineage_builder import build_lineage

    ctx.lineage = build_lineage(
        ctx.artifacts.manifest,
        ctx.models,
        ctx.sources,
        ctx.seeds,
        ctx.snapshots,
        layer_config=ctx.layer_config,
        exclude_packages=ctx.exclude_packages,
    )


def stage_build_search_index(ctx: PipelineContext) -> None:
    """Build the full-text search index."""
    from docglow.generator.search_index import build_search_index

    ctx.search_index = build_search_index(ctx.models, ctx.sources, ctx.seeds, ctx.snapshots)


def stage_compute_health(ctx: PipelineContext) -> None:
    """Compute project health scores."""
    from docglow.analyzer.health import compute_health, health_to_dict

    report = compute_health(ctx.models, ctx.sources, ctx.seeds, ctx.snapshots)
    ctx.health = health_to_dict(report)


def stage_build_column_lineage(ctx: PipelineContext) -> None:
    """Build column-level lineage (optional, requires sqlglot)."""
    if not ctx.column_lineage_enabled:
        return

    from docglow.generator.data import _build_column_lineage

    ctx.column_lineage = _build_column_lineage(
        ctx.column_lineage_enabled,
        ctx.column_lineage_select,
        ctx.column_lineage_depth,
        ctx.column_lineage_cache_dir,
        ctx.artifacts.manifest,
        ctx.models,
        ctx.sources,
        ctx.seeds,
        ctx.snapshots,
    )


def stage_strip_sql(ctx: PipelineContext) -> None:
    """Strip raw_sql and compiled_sql from all nodes when --slim is enabled.

    This runs AFTER lineage/health/search analysis so those stages can use the
    SQL, but BEFORE JSON serialization so the output payload is smaller.
    """
    if not ctx.slim:
        return

    for collection in (ctx.models, ctx.seeds, ctx.snapshots):
        for uid in collection:
            collection[uid] = {
                **collection[uid],
                "raw_sql": "",
                "compiled_sql": "",
            }


def stage_build_ai_context(ctx: PipelineContext) -> None:
    """Build AI context for chat panel (optional)."""
    if not ctx.ai_enabled:
        return

    from docglow.ai.context import build_ai_context

    ctx.ai_context = build_ai_context(
        ctx.models,
        ctx.sources,
        ctx.seeds,
        metadata={
            "project_name": ctx.artifacts.manifest.metadata.project_name or "",
            "dbt_version": ctx.artifacts.manifest.metadata.dbt_version,
        },
        health=ctx.health,
    )


def stage_build_metadata(ctx: PipelineContext) -> None:
    """Build the metadata dict and resolve AI key."""
    manifest = ctx.artifacts.manifest
    catalog = ctx.artifacts.catalog
    run_results = ctx.artifacts.run_results

    ctx.metadata = {
        "generated_at": manifest.metadata.generated_at,
        "docglow_version": __version__,
        "dbt_version": manifest.metadata.dbt_version,
        "project_name": manifest.metadata.project_name or "",
        "project_id": manifest.metadata.project_id or "",
        "target_name": "",
        "artifact_versions": {
            "manifest": manifest.metadata.dbt_schema_version,
            "catalog": catalog.metadata.dbt_schema_version,
            "run_results": (run_results.metadata.dbt_schema_version if run_results else None),
            "sources": None,
        },
        "profiling_enabled": ctx.profiling_enabled,
        "ai_enabled": ctx.ai_enabled,
        "hosted": False,
        "workspace_slug": None,
        "project_slug": None,
        "api_base_url": None,
        "published_at": None,
    }


# ---------------------------------------------------------------------------
# Default pipeline
# ---------------------------------------------------------------------------


def default_stages(ctx: PipelineContext) -> list[PipelineStage]:
    """Return the default ordered list of pipeline stages."""
    return [
        PipelineStage("build_lookups", stage_build_lookups),
        PipelineStage("transform_nodes", stage_transform_nodes),
        PipelineStage("filter_nodes", stage_filter_nodes),
        PipelineStage("transform_sources", stage_transform_sources),
        PipelineStage("transform_exposures_metrics", stage_transform_exposures_metrics),
        PipelineStage("build_lineage", stage_build_lineage),
        PipelineStage("build_search_index", stage_build_search_index),
        PipelineStage("compute_health", stage_compute_health),
        PipelineStage(
            "build_column_lineage",
            stage_build_column_lineage,
            enabled=ctx.column_lineage_enabled,
        ),
        PipelineStage("strip_sql", stage_strip_sql, enabled=ctx.slim),
        PipelineStage(
            "build_ai_context",
            stage_build_ai_context,
            enabled=ctx.ai_enabled,
        ),
        PipelineStage("build_metadata", stage_build_metadata),
    ]


def context_to_dict(ctx: PipelineContext) -> dict[str, Any]:
    """Convert pipeline context to the final JSON-serializable dict."""
    resolved_ai_key: str | None = None
    if ctx.ai_enabled:
        resolved_ai_key = ctx.ai_key or os.environ.get("ANTHROPIC_API_KEY")

    return {
        "metadata": ctx.metadata,
        "models": ctx.models,
        "sources": ctx.sources,
        "seeds": ctx.seeds,
        "snapshots": ctx.snapshots,
        "exposures": ctx.exposures,
        "metrics": ctx.metrics,
        "lineage": ctx.lineage,
        "health": ctx.health,
        "search_index": ctx.search_index,
        "ai_context": ctx.ai_context,
        "ai_key": resolved_ai_key,
        "column_lineage": ctx.column_lineage,
    }
