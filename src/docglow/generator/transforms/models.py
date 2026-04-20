"""Transform dbt manifest nodes into Docglow model dicts."""

from __future__ import annotations

from typing import Any

from docglow.artifacts.catalog import Catalog, CatalogColumnInfo
from docglow.artifacts.manifest import ManifestNode
from docglow.artifacts.run_results import RunResult


def transform_model(
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
        "path": node.original_file_path.replace("\\", "/"),
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


def _get_folder(path: str) -> str:
    """Extract the folder from a model path.

    Normalizes backslashes to forward slashes first, since dbt on Windows
    writes paths with backslashes in the manifest (e.g. ``models\\billing\\base\\model.sql``).
    """
    normalized = path.replace("\\", "/")
    parts = normalized.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else ""


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
            status = normalize_test_status(result.status)

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
            status = normalize_test_status(run_result.status)
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


def normalize_test_status(status: str) -> str:
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
