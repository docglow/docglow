"""Transform dbt artifacts into the unified DocglowData JSON payload."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from docglow import __version__
from docglow.analyzer.health import compute_health, health_to_dict
from docglow.artifacts.catalog import Catalog, CatalogColumnInfo
from docglow.artifacts.loader import LoadedArtifacts
from docglow.artifacts.manifest import Manifest, ManifestNode, ManifestSource
from docglow.artifacts.run_results import RunResult, RunResults
from docglow.generator.filters import filter_resources as _filter_resources
from docglow.generator.layers import LineageLayerConfig
from docglow.generator.lineage_builder import build_lineage as _build_lineage
from docglow.generator.search_index import build_search_index as _build_search_index


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
    run_results_by_id = _build_run_results_map(run_results)
    test_nodes_by_model = _build_test_map(manifest)
    reverse_deps = _build_reverse_dependency_map(manifest)

    # Transform models, seeds, snapshots
    models: dict[str, Any] = {}
    seeds: dict[str, Any] = {}
    snapshots: dict[str, Any] = {}

    for unique_id, node in manifest.nodes.items():
        is_package = bool(root_project_name and node.package_name != root_project_name)
        if node.resource_type == "model":
            model_data = _transform_model(
                node, catalog, run_results_by_id, test_nodes_by_model, reverse_deps
            )
            model_data["is_package"] = is_package
            models[unique_id] = model_data
        elif node.resource_type == "seed":
            seed_data = _transform_model(
                node, catalog, run_results_by_id, test_nodes_by_model, reverse_deps
            )
            seed_data["is_package"] = is_package
            seeds[unique_id] = seed_data
        elif node.resource_type == "snapshot":
            snap_data = _transform_model(
                node, catalog, run_results_by_id, test_nodes_by_model, reverse_deps
            )
            snap_data["is_package"] = is_package
            snapshots[unique_id] = snap_data

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
        sources[unique_id] = _transform_source(source, catalog, artifacts.source_freshness)

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
    column_lineage: dict[str, Any] | None = None
    if column_lineage_enabled:
        from pathlib import Path as _Path

        from docglow.lineage.analyzer import analyze_column_lineage
        from docglow.lineage.column_parser import detect_dialect

        dialect = detect_dialect(manifest.metadata.adapter_type)

        subset = None
        if column_lineage_select:
            from docglow.lineage.analyzer import compute_column_lineage_subset

            subset = compute_column_lineage_subset(
                pattern=column_lineage_select,
                models=models,
                sources=sources,
                seeds=seeds,
                snapshots=snapshots,
                max_depth=column_lineage_depth,
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
                _Path(column_lineage_cache_dir) / ".docglow-column-lineage-cache.json"
                if column_lineage_cache_dir
                else _Path(".docglow-column-lineage-cache.json")
            ),
            subset=subset,
        )

        # Backfill columns for models that have lineage but no catalog/manifest columns.
        # This happens with Dynamic Tables and models not yet compiled.
        if column_lineage:
            _backfill_columns_from_lineage(column_lineage, models, seeds, snapshots)

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


def _build_run_results_map(
    run_results: RunResults | None,
) -> dict[str, RunResult]:
    """Map unique_id -> RunResult for quick lookup."""
    if run_results is None:
        return {}
    return {r.unique_id: r for r in run_results.results}


def _build_test_map(
    manifest: Manifest,
) -> dict[str, list[ManifestNode]]:
    """Map model unique_id -> list of test nodes that depend on it."""
    test_map: dict[str, list[ManifestNode]] = {}
    for node in manifest.nodes.values():
        if node.resource_type != "test":
            continue
        for dep_id in node.depends_on.nodes:
            if dep_id not in test_map:
                test_map[dep_id] = []
            test_map[dep_id].append(node)
    return test_map


def _build_reverse_dependency_map(manifest: Manifest) -> dict[str, list[str]]:
    """Build a map of unique_id -> list of unique_ids that depend on it."""
    if manifest.child_map:
        return dict(manifest.child_map)

    reverse: dict[str, list[str]] = {}
    for unique_id, node in manifest.nodes.items():
        if node.resource_type in ("test", "operation"):
            continue
        for dep_id in node.depends_on.nodes:
            if dep_id not in reverse:
                reverse[dep_id] = []
            reverse[dep_id].append(unique_id)
    return reverse


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


def _get_folder(path: str) -> str:
    """Extract the folder from a model path."""
    parts = path.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else ""


def _transform_model(
    node: ManifestNode,
    catalog: Catalog,
    run_results_by_id: dict[str, RunResult],
    test_nodes_by_model: dict[str, list[ManifestNode]],
    reverse_deps: dict[str, list[str]],
) -> dict[str, Any]:
    """Transform a manifest node + catalog data into a DocglowModel dict."""
    catalog_node = catalog.nodes.get(node.unique_id)

    # Merge column info from manifest + catalog
    columns = _merge_columns(node, catalog_node, run_results_by_id, test_nodes_by_model)

    # Build test results for this model
    test_results = _build_test_results(node.unique_id, test_nodes_by_model, run_results_by_id)

    # Model run result
    model_result = run_results_by_id.get(node.unique_id)
    last_run = None
    if model_result:
        completed_at = None
        if model_result.timing:
            completed_at = model_result.timing[-1].completed_at
        last_run = {
            "status": model_result.status,
            "execution_time": model_result.execution_time,
            "completed_at": completed_at,
        }

    # Catalog stats
    catalog_stats = {"row_count": None, "bytes": None, "has_stats": False}
    if catalog_node and catalog_node.stats:
        has_stats_entry = catalog_node.stats.get("has_stats")
        if has_stats_entry:
            catalog_stats["has_stats"] = bool(has_stats_entry.value)
        row_count_entry = catalog_node.stats.get("row_count")
        if row_count_entry and row_count_entry.value is not None:
            try:
                catalog_stats["row_count"] = int(row_count_entry.value)  # type: ignore[call-overload]
            except (ValueError, TypeError):
                pass
        bytes_entry = catalog_node.stats.get("bytes")
        if bytes_entry and bytes_entry.value is not None:
            try:
                catalog_stats["bytes"] = int(bytes_entry.value)  # type: ignore[call-overload]
            except (ValueError, TypeError):
                pass

    # Extract source refs
    sources_used = [
        f"source.{node.package_name}.{s[0]}.{s[1]}"
        if isinstance(s, list | tuple) and len(s) >= 2
        else str(s)
        for s in node.sources
    ]

    # Filter reverse deps to exclude tests
    referenced_by = [
        ref for ref in reverse_deps.get(node.unique_id, []) if not ref.startswith("test.")
    ]

    return {
        "unique_id": node.unique_id,
        "name": node.name,
        "description": node.description,
        "schema": node.schema_ or "",
        "database": node.database or "",
        "materialization": (node.config.materialized or ""),
        "tags": list(node.tags),
        "meta": dict(node.meta),
        "path": node.original_file_path,
        "folder": _get_folder(node.original_file_path),
        "raw_sql": node.raw_code,
        "compiled_sql": node.compiled_code or "",
        "columns": columns,
        "depends_on": [d for d in node.depends_on.nodes if not d.startswith("test.")],
        "referenced_by": referenced_by,
        "sources_used": sources_used,
        "test_results": test_results,
        "last_run": last_run,
        "catalog_stats": catalog_stats,
    }


def _merge_columns(
    node: ManifestNode,
    catalog_node: Any | None,
    run_results_by_id: dict[str, RunResult],
    test_nodes_by_model: dict[str, list[ManifestNode]],
) -> list[dict[str, Any]]:
    """Merge column info from manifest (descriptions) and catalog (types)."""
    # Start with catalog columns (they have the actual types)
    catalog_columns: dict[str, CatalogColumnInfo] = {}
    if catalog_node and catalog_node.columns:
        catalog_columns = catalog_node.columns

    # Get manifest columns (descriptions, meta, tags)
    manifest_columns = node.columns

    # Collect all column names (union of catalog and manifest)
    all_column_names: list[str] = []
    seen: set[str] = set()

    # Catalog columns first (preserves column order via index)
    sorted_catalog = sorted(catalog_columns.values(), key=lambda c: c.index)
    for col in sorted_catalog:
        lower_name = col.name.lower()
        if lower_name not in seen:
            all_column_names.append(col.name)
            seen.add(lower_name)

    # Then any manifest-only columns
    for col_name in manifest_columns:
        if col_name.lower() not in seen:
            all_column_names.append(col_name)
            seen.add(col_name.lower())

    # Build column tests map
    column_tests = _build_column_tests(node.unique_id, test_nodes_by_model, run_results_by_id)

    columns: list[dict[str, Any]] = []
    for col_name in all_column_names:
        catalog_col = catalog_columns.get(col_name) or catalog_columns.get(col_name.lower())
        manifest_col = manifest_columns.get(col_name) or manifest_columns.get(col_name.lower())

        columns.append(
            {
                "name": col_name,
                "description": manifest_col.description if manifest_col else "",
                "data_type": catalog_col.type if catalog_col else "",
                "meta": dict(manifest_col.meta) if manifest_col else {},
                "tags": list(manifest_col.tags) if manifest_col else [],
                "tests": column_tests.get(col_name.lower(), []),
                "profile": None,
            }
        )

    return columns


def _build_column_tests(
    model_id: str,
    test_nodes_by_model: dict[str, list[ManifestNode]],
    run_results_by_id: dict[str, RunResult],
) -> dict[str, list[dict[str, Any]]]:
    """Build a map of column_name -> list of test dicts."""
    column_tests: dict[str, list[dict[str, Any]]] = {}

    for test_node in test_nodes_by_model.get(model_id, []):
        if not test_node.column_name:
            continue

        col_lower = test_node.column_name.lower()
        test_type = ""
        if test_node.test_metadata:
            test_type = test_node.test_metadata.name

        result = run_results_by_id.get(test_node.unique_id)
        status = "not_run"
        if result:
            status = _normalize_test_status(result.status)

        test_entry = {
            "test_name": test_node.name,
            "test_type": test_type,
            "status": status,
            "config": {},
        }

        if test_node.test_metadata and test_type == "accepted_values":
            kwargs = test_node.test_metadata.kwargs
            test_entry["config"] = {"values": kwargs.get("values", [])}

        if col_lower not in column_tests:
            column_tests[col_lower] = []
        column_tests[col_lower].append(test_entry)

    return column_tests


def _build_test_results(
    model_id: str,
    test_nodes_by_model: dict[str, list[ManifestNode]],
    run_results_by_id: dict[str, RunResult],
) -> list[dict[str, Any]]:
    """Build test result dicts for a model."""
    results: list[dict[str, Any]] = []

    for test_node in test_nodes_by_model.get(model_id, []):
        test_type = ""
        if test_node.test_metadata:
            test_type = test_node.test_metadata.name

        run_result = run_results_by_id.get(test_node.unique_id)
        status = "not_run"
        execution_time = 0.0
        failures = 0
        message = None

        if run_result:
            status = _normalize_test_status(run_result.status)
            execution_time = run_result.execution_time
            failures = run_result.failures or 0
            message = run_result.message

        results.append(
            {
                "test_name": test_node.name,
                "test_type": test_type,
                "column_name": test_node.column_name,
                "status": status,
                "execution_time": execution_time,
                "failures": failures,
                "message": message,
            }
        )

    return results


def _normalize_test_status(status: str) -> str:
    """Normalize dbt test status to our standard values."""
    mapping = {
        "success": "pass",
        "pass": "pass",
        "fail": "fail",
        "failure": "fail",
        "error": "error",
        "warn": "warn",
        "warning": "warn",
        "skipped": "not_run",
    }
    return mapping.get(status.lower(), status)


def _transform_source(
    source: ManifestSource,
    catalog: Catalog,
    source_freshness: Any | None,
) -> dict[str, Any]:
    """Transform a manifest source into a DocglowSource dict."""
    catalog_node = catalog.sources.get(source.unique_id)

    # Merge columns
    catalog_columns: dict[str, Any] = {}
    if catalog_node and catalog_node.columns:
        catalog_columns = catalog_node.columns

    columns: list[dict[str, Any]] = []
    seen: set[str] = set()

    sorted_catalog = sorted(catalog_columns.values(), key=lambda c: c.index)
    for col in sorted_catalog:
        lower_name = col.name.lower()
        if lower_name not in seen:
            manifest_col = source.columns.get(col.name) or source.columns.get(col.name.lower())
            columns.append(
                {
                    "name": col.name,
                    "description": manifest_col.description if manifest_col else "",
                    "data_type": col.type if hasattr(col, "type") else "",
                    "meta": dict(manifest_col.meta) if manifest_col else {},
                    "tags": list(manifest_col.tags) if manifest_col else [],
                    "tests": [],
                    "profile": None,
                }
            )
            seen.add(lower_name)

    # Freshness info
    freshness_status = None
    freshness_max_loaded_at = None
    freshness_snapshotted_at = None

    if source_freshness:
        for fr in source_freshness.results:
            if fr.unique_id == source.unique_id:
                freshness_status = fr.status
                freshness_max_loaded_at = fr.max_loaded_at
                freshness_snapshotted_at = fr.snapshotted_at
                break

    return {
        "unique_id": source.unique_id,
        "name": source.name,
        "source_name": source.source_name,
        "description": source.description or source.source_description,
        "schema": source.schema_ or "",
        "database": source.database or "",
        "columns": columns,
        "tags": list(source.tags),
        "meta": dict(source.meta),
        "loader": source.loader,
        "loaded_at_field": source.loaded_at_field,
        "freshness_status": freshness_status,
        "freshness_max_loaded_at": freshness_max_loaded_at,
        "freshness_snapshotted_at": freshness_snapshotted_at,
    }
