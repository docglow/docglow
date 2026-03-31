"""Transform dbt artifacts into the unified DocglowData JSON payload."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docglow.artifacts.loader import LoadedArtifacts
from docglow.generator.layers import LineageLayerConfig


@dataclass(frozen=True)
class DocglowColumnTest:
    test_name: str
    test_type: str
    status: str  # pass | fail | warn | error | not_run
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocglowColumn:
    name: str
    description: str
    data_type: str
    meta: dict[str, Any]
    tags: list[str]
    tests: list[DocglowColumnTest]
    profile: None = None  # Populated in Phase 2


@dataclass(frozen=True)
class DocglowTestResult:
    test_name: str
    test_type: str
    column_name: str | None
    status: str
    execution_time: float
    failures: int
    message: str | None


@dataclass(frozen=True)
class DocglowLastRun:
    status: str | None
    execution_time: float | None
    completed_at: str | None


@dataclass(frozen=True)
class DocglowCatalogStats:
    row_count: int | None
    bytes: int | None
    has_stats: bool


@dataclass(frozen=True)
class DocglowModel:
    unique_id: str
    name: str
    description: str
    schema: str
    database: str
    materialization: str
    tags: list[str]
    meta: dict[str, Any]
    path: str
    folder: str
    raw_sql: str
    compiled_sql: str
    columns: list[DocglowColumn]
    depends_on: list[str]
    referenced_by: list[str]
    sources_used: list[str]
    test_results: list[DocglowTestResult]
    last_run: DocglowLastRun | None
    catalog_stats: DocglowCatalogStats


@dataclass(frozen=True)
class DocglowSource:
    unique_id: str
    name: str
    source_name: str
    description: str
    schema: str
    database: str
    columns: list[DocglowColumn]
    tags: list[str]
    meta: dict[str, Any]
    loader: str
    loaded_at_field: str | None
    freshness_status: str | None
    freshness_max_loaded_at: str | None
    freshness_snapshotted_at: str | None


@dataclass(frozen=True)
class LineageNode:
    id: str
    name: str
    resource_type: str
    materialization: str
    schema: str
    test_status: str  # pass | fail | warn | none
    has_description: bool
    folder: str
    tags: list[str]


@dataclass(frozen=True)
class LineageEdge:
    source: str
    target: str


@dataclass(frozen=True)
class SearchEntry:
    unique_id: str
    name: str
    resource_type: str
    description: str
    columns: str
    tags: str
    sql_snippet: str


@dataclass(frozen=True)
class DocglowMetadata:
    generated_at: str
    docglow_version: str
    dbt_version: str
    project_name: str
    project_id: str
    target_name: str
    artifact_versions: dict[str, str | None]
    profiling_enabled: bool
    ai_enabled: bool
    hosted: bool = False
    workspace_slug: str | None = None
    project_slug: str | None = None
    api_base_url: str | None = None
    published_at: str | None = None


@dataclass(frozen=True)
class DocglowData:
    metadata: DocglowMetadata
    models: dict[str, dict[str, Any]]
    sources: dict[str, dict[str, Any]]
    seeds: dict[str, dict[str, Any]]
    snapshots: dict[str, dict[str, Any]]
    exposures: dict[str, dict[str, Any]]
    metrics: dict[str, dict[str, Any]]
    lineage: dict[str, Any]
    health: dict[str, Any]
    search_index: list[dict[str, Any]]


def build_docglow_data(
    artifacts: LoadedArtifacts,
    *,
    profiling_enabled: bool = False,
    ai_enabled: bool = False,
    ai_key: str | None = None,
    select: str | None = None,
    exclude: str | None = None,
    layer_config: LineageLayerConfig | None = None,
    column_lineage_enabled: bool = False,
    column_lineage_select: str | None = None,
    column_lineage_depth: int | None = None,
    column_lineage_cache_dir: Any | None = None,
    exclude_packages: bool = True,
    slim: bool = False,
) -> dict[str, Any]:
    """Transform loaded artifacts into the unified DocglowData payload.

    Delegates to the generation pipeline, which executes discrete named stages.
    Returns a plain dict suitable for JSON serialization.
    """
    from docglow.generator.pipeline import (
        PipelineContext,
        context_to_dict,
        default_stages,
        run_pipeline,
    )

    ctx = PipelineContext(
        artifacts=artifacts,
        profiling_enabled=profiling_enabled,
        ai_enabled=ai_enabled,
        ai_key=ai_key,
        select=select,
        exclude=exclude,
        layer_config=layer_config or LineageLayerConfig(),
        column_lineage_enabled=column_lineage_enabled,
        column_lineage_select=column_lineage_select,
        column_lineage_depth=column_lineage_depth,
        column_lineage_cache_dir=column_lineage_cache_dir,
        exclude_packages=exclude_packages,
        slim=slim,
    )

    stages = default_stages(ctx)
    run_pipeline(stages, ctx)

    return context_to_dict(ctx)


def _build_column_lineage(
    enabled: bool,
    select: str | None,
    depth: int | None,
    cache_dir: Any | None,
    manifest: Any,
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
) -> dict[str, Any] | None:
    """Build column-level lineage if enabled."""
    if not enabled:
        return None

    from pathlib import Path as _Path

    from docglow.lineage.analyzer import analyze_column_lineage
    from docglow.lineage.column_parser import detect_dialect

    dialect = detect_dialect(manifest.metadata.adapter_type)

    subset = None
    if select:
        from docglow.lineage.analyzer import compute_column_lineage_subset

        subset = compute_column_lineage_subset(
            pattern=select,
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            max_depth=depth,
        )

    column_lineage = analyze_column_lineage(
        models=models,
        sources=sources,
        seeds=seeds,
        snapshots=snapshots,
        dialect=dialect,
        manifest_nodes=dict(manifest.nodes),
        manifest_sources=dict(manifest.sources),
        cache_path=(
            _Path(cache_dir) / ".docglow-column-lineage-cache.json"
            if cache_dir
            else _Path(".docglow-column-lineage-cache.json")
        ),
        subset=subset,
    )

    # Backfill columns for models that have lineage but no catalog/manifest columns.
    if column_lineage:
        _backfill_columns_from_lineage(column_lineage, models, seeds, snapshots)

    return column_lineage


def _backfill_columns_from_lineage(
    column_lineage: dict[str, dict[str, list[dict[str, str]]]],
    *collections: dict[str, Any],
) -> None:
    """Add placeholder column entries for models that have lineage but no columns.

    Dynamic Tables and uncompiled models often have no catalog or manifest
    column data, but column lineage analysis can still resolve their output
    columns from CTE definitions. This backfills the model's ``columns``
    list so the frontend can display them.
    """
    for collection in collections:
        for uid, model_data in collection.items():
            if uid not in column_lineage:
                continue
            if model_data.get("columns"):
                continue  # Already has columns

            lineage_cols = column_lineage[uid]
            model_data["columns"] = [
                {
                    "name": col_name,
                    "description": "",
                    "data_type": "",
                    "meta": {},
                    "tags": [],
                    "tests": [],
                    "profile": None,
                }
                for col_name in sorted(lineage_cols.keys())
            ]
