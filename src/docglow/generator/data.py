"""Transform dbt artifacts into the unified DocglowData JSON payload."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from typing import Any

from docglow import __version__
from docglow.analyzer.health import compute_health, health_to_dict
from docglow.artifacts.catalog import Catalog, CatalogColumnInfo
from docglow.artifacts.loader import LoadedArtifacts
from docglow.artifacts.manifest import Manifest, ManifestNode, ManifestSource
from docglow.artifacts.run_results import RunResult, RunResults
from docglow.generator.layers import LineageLayerConfig, layers_to_dict, resolve_all_layers


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
        from docglow.lineage.analyzer import analyze_column_lineage
        from docglow.lineage.column_parser import detect_dialect

        dialect = detect_dialect(manifest.metadata.adapter_type)
        column_lineage = analyze_column_lineage(
            models=models,
            sources=sources,
            seeds=seeds,
            snapshots=snapshots,
            dialect=dialect,
            manifest_nodes=dict(manifest.nodes),
            manifest_sources=dict(manifest.sources),
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


def _filter_resources(
    models: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    select: str | None = None,
    exclude: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Filter models/seeds/snapshots by --select and --exclude patterns.

    Supports:
      - Glob patterns matching model name: ``stg_*``, ``*orders*``
      - Folder paths: ``staging/*``, ``marts/finance/*``
      - ``+name`` prefix: include all upstream dependencies
      - ``name+`` suffix: include all downstream dependents
    """
    all_resources = {**models, **seeds, **snapshots}

    if select:
        selected = _resolve_selection(select, all_resources)
    else:
        selected = set(all_resources.keys())

    if exclude:
        excluded = _resolve_selection(exclude, all_resources)
        selected -= excluded

    return (
        {k: v for k, v in models.items() if k in selected},
        {k: v for k, v in seeds.items() if k in selected},
        {k: v for k, v in snapshots.items() if k in selected},
    )


def _resolve_selection(
    pattern: str,
    resources: dict[str, Any],
) -> set[str]:
    """Resolve a selection pattern to a set of unique_ids."""
    include_upstream = pattern.startswith("+")
    include_downstream = pattern.endswith("+")
    clean = pattern.strip("+")

    matched: set[str] = set()
    for uid, data in resources.items():
        name = data.get("name", "")
        folder = data.get("folder", "")
        path = data.get("path", "")

        matches_filter = (
            fnmatch.fnmatch(name, clean)
            or fnmatch.fnmatch(folder, clean)
            or fnmatch.fnmatch(path, clean)
        )
        if matches_filter:
            matched.add(uid)

    if include_upstream:
        upstream: set[str] = set()
        for uid in matched:
            _collect_upstream(uid, resources, upstream)
        matched |= upstream

    if include_downstream:
        downstream: set[str] = set()
        for uid in matched:
            _collect_downstream(uid, resources, downstream)
        matched |= downstream

    return matched


def _collect_upstream(
    uid: str,
    resources: dict[str, Any],
    visited: set[str],
) -> None:
    """Recursively collect upstream dependencies."""
    data = resources.get(uid)
    if not data:
        return
    for dep in data.get("depends_on", []):
        if dep not in visited and dep in resources:
            visited.add(dep)
            _collect_upstream(dep, resources, visited)


def _collect_downstream(
    uid: str,
    resources: dict[str, Any],
    visited: set[str],
) -> None:
    """Recursively collect downstream dependents."""
    data = resources.get(uid)
    if not data:
        return
    for ref in data.get("referenced_by", []):
        if ref not in visited and ref in resources:
            visited.add(ref)
            _collect_downstream(ref, resources, visited)


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


def _build_lineage(
    manifest: Manifest,
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    layer_config: LineageLayerConfig,
    exclude_packages: bool = True,
) -> dict[str, Any]:
    """Build lineage graph nodes and edges."""
    # Determine which node IDs to exclude (package models/seeds/snapshots)
    excluded_ids: set[str] = set()
    if exclude_packages:
        for collection in (models, seeds, snapshots):
            for uid, data in collection.items():
                if data.get("is_package", False):
                    excluded_ids.add(uid)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()

    def _add_lineage_node(
        unique_id: str,
        name: str,
        resource_type: str,
        materialization: str,
        schema: str,
        test_status: str,
        has_description: bool,
        folder: str,
        tags: list[str],
        meta: dict[str, Any] | None = None,
    ) -> None:
        if unique_id in seen_node_ids:
            return
        seen_node_ids.add(unique_id)
        nodes.append(
            {
                "id": unique_id,
                "name": name,
                "resource_type": resource_type,
                "materialization": materialization,
                "schema": schema,
                "test_status": test_status,
                "has_description": has_description,
                "folder": folder,
                "tags": tags,
                "meta": meta or {},
            }
        )

    def _get_test_status(model_data: dict[str, Any]) -> str:
        test_results = model_data.get("test_results", [])
        if not test_results:
            return "none"
        statuses = {t["status"] for t in test_results}
        if "fail" in statuses or "error" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        if "pass" in statuses:
            return "pass"
        return "none"

    # Add model/seed/snapshot nodes
    for collection, resource_type in [
        (models, "model"),
        (seeds, "seed"),
        (snapshots, "snapshot"),
    ]:
        for uid, data in collection.items():
            if uid in excluded_ids:
                continue
            _add_lineage_node(
                unique_id=uid,
                name=data["name"],
                resource_type=resource_type,
                materialization=data.get("materialization", ""),
                schema=data.get("schema", ""),
                test_status=_get_test_status(data),
                has_description=bool(data.get("description")),
                folder=data.get("folder", ""),
                tags=data.get("tags", []),
                meta=data.get("meta", {}),
            )
            for dep in data.get("depends_on", []):
                if dep not in excluded_ids:
                    edges.append({"source": dep, "target": uid})

    # Add source nodes
    for uid, data in sources.items():
        _add_lineage_node(
            unique_id=uid,
            name=f"{data['source_name']}.{data['name']}",
            resource_type="source",
            materialization="",
            schema=data.get("schema", ""),
            test_status="none",
            has_description=bool(data.get("description")),
            folder="",
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
        )

    # Add exposure nodes from manifest
    for uid, exposure in manifest.exposures.items():
        _add_lineage_node(
            unique_id=uid,
            name=exposure.name,
            resource_type="exposure",
            materialization="",
            schema="",
            test_status="none",
            has_description=bool(exposure.description),
            folder="",
            tags=list(exposure.tags),
        )
        for dep in exposure.depends_on.nodes:
            if dep not in excluded_ids:
                edges.append({"source": dep, "target": uid})

    # Resolve layer ranks for all nodes
    layer_ranks, auto_assigned = resolve_all_layers(nodes, edges, layer_config)
    for node in nodes:
        node["layer"] = layer_ranks.get(node["id"])
        node["layer_auto"] = node["id"] in auto_assigned
        # Remove meta from lineage output (only needed for layer resolution)
        node.pop("meta", None)

    return {
        "nodes": nodes,
        "edges": edges,
        "layer_config": layers_to_dict(layer_config),
    }


def _build_search_index(
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the search index for Fuse.js."""
    entries: list[dict[str, Any]] = []

    for collection, resource_type in [
        (models, "model"),
        (sources, "source"),
        (seeds, "seed"),
        (snapshots, "snapshot"),
    ]:
        for uid, data in collection.items():
            column_names = [c["name"] for c in data.get("columns", [])]
            sql = data.get("compiled_sql", "") or data.get("raw_sql", "")

            entries.append(
                {
                    "unique_id": uid,
                    "name": data.get("name", ""),
                    "resource_type": resource_type,
                    "description": data.get("description", ""),
                    "columns": ", ".join(column_names),
                    "tags": ", ".join(data.get("tags", [])),
                    "sql_snippet": sql[:500],
                }
            )

    return entries
