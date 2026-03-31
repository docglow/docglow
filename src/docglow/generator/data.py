"""Transform dbt artifacts into the unified DocglowData JSON payload."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from docglow import __version__
from docglow.analyzer.health import compute_health, health_to_dict
from docglow.artifacts.loader import LoadedArtifacts
from docglow.generator.filters import filter_resources as _filter_resources
from docglow.generator.layers import LineageLayerConfig
from docglow.generator.lineage_builder import build_lineage as _build_lineage
from docglow.generator.search_index import build_search_index as _build_search_index
from docglow.generator.transforms.lookups import (
    build_reverse_dependency_map,
    build_run_results_map,
    build_test_map,
)
from docglow.generator.transforms.models import transform_model
from docglow.generator.transforms.sources import transform_source


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
) -> dict[str, Any]:
    """Transform loaded artifacts into the unified DocglowData payload.

    Returns a plain dict suitable for JSON serialization.
    """
    manifest = artifacts.manifest
    catalog = artifacts.catalog
    run_results = artifacts.run_results

    # Determine root project name for package filtering
    root_project_name = manifest.metadata.project_name or ""

    # Build lookup maps
    run_results_by_id = build_run_results_map(run_results)
    test_nodes_by_model = build_test_map(manifest)
    reverse_deps = build_reverse_dependency_map(manifest)

    # Transform models, seeds, snapshots
    models: dict[str, Any] = {}
    seeds: dict[str, Any] = {}
    snapshots: dict[str, Any] = {}

    for unique_id, node in manifest.nodes.items():
        is_package = bool(root_project_name and node.package_name != root_project_name)
        if node.resource_type in ("model", "seed", "snapshot"):
            data = transform_model(
                node, catalog, run_results_by_id, test_nodes_by_model, reverse_deps
            )
            data["is_package"] = is_package
            if node.resource_type == "model":
                models[unique_id] = data
            elif node.resource_type == "seed":
                seeds[unique_id] = data
            else:
                snapshots[unique_id] = data

    # Apply --select / --exclude filtering
    if select or exclude:
        models, seeds, snapshots = _filter_resources(
            models,
            seeds,
            snapshots,
            select=select,
            exclude=exclude,
        )

    # Transform sources
    sources: dict[str, Any] = {}
    for unique_id, source in manifest.sources.items():
        sources[unique_id] = transform_source(source, catalog, artifacts.source_freshness)

    # Transform exposures
    exposures: dict[str, Any] = {}
    for unique_id, exposure in manifest.exposures.items():
        exposures[unique_id] = {
            "unique_id": unique_id,
            "name": exposure.name,
            "type": exposure.type,
            "description": exposure.description,
            "depends_on": exposure.depends_on.nodes,
            "owner": dict(exposure.owner),
            "tags": list(exposure.tags),
        }

    # Transform metrics
    metrics: dict[str, Any] = {}
    for unique_id, metric in manifest.metrics.items():
        metrics[unique_id] = {
            "unique_id": unique_id,
            "name": metric.name,
            "description": metric.description,
            "label": metric.label,
            "type": metric.type,
            "depends_on": metric.depends_on.nodes,
            "tags": list(metric.tags),
        }

    # Build lineage graph
    lineage = _build_lineage(
        manifest,
        models,
        sources,
        seeds,
        snapshots,
        layer_config=layer_config or LineageLayerConfig(),
        exclude_packages=exclude_packages,
    )

    # Build search index
    search_index = _build_search_index(models, sources, seeds, snapshots)

    # Health analysis
    health_report = compute_health(models, sources, seeds, snapshots)
    health = health_to_dict(health_report)

    # Column-level lineage
    column_lineage = _build_column_lineage(
        column_lineage_enabled,
        column_lineage_select,
        column_lineage_depth,
        column_lineage_cache_dir,
        manifest,
        models,
        sources,
        seeds,
        snapshots,
    )

    # AI context (compact project summary for chat)
    ai_context: dict[str, Any] | None = None
    if ai_enabled:
        from docglow.ai.context import build_ai_context

        ai_context = build_ai_context(
            models,
            sources,
            seeds,
            metadata={
                "project_name": manifest.metadata.project_name or "",
                "dbt_version": manifest.metadata.dbt_version,
            },
            health=health,
        )

    # Metadata
    metadata = {
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
        "profiling_enabled": profiling_enabled,
        "ai_enabled": ai_enabled,
        "hosted": False,
        "workspace_slug": None,
        "project_slug": None,
        "api_base_url": None,
        "published_at": None,
    }

    # Resolve AI key: explicit param > env var
    resolved_ai_key: str | None = None
    if ai_enabled:
        resolved_ai_key = ai_key or os.environ.get("ANTHROPIC_API_KEY")

    return {
        "metadata": metadata,
        "models": models,
        "sources": sources,
        "seeds": seeds,
        "snapshots": snapshots,
        "exposures": exposures,
        "metrics": metrics,
        "lineage": lineage,
        "health": health,
        "search_index": search_index,
        "ai_context": ai_context,
        "ai_key": resolved_ai_key,
        "column_lineage": column_lineage,
    }


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
