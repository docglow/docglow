"""MCP tool definitions and implementations.

Each tool is a pure function that queries the in-memory docglow data.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """An MCP tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], dict[str, Any]], Any]


def _list_models(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """List all models with optional filtering."""
    models = data["models"]
    name_pattern = params.get("name_pattern")
    folder = params.get("folder")
    tag = params.get("tag")
    include_packages = params.get("include_packages", False)

    results: list[dict[str, Any]] = []
    for uid, model in models.items():
        if not include_packages and model.get("is_package", False):
            continue
        if name_pattern and not fnmatch.fnmatch(model["name"], name_pattern):
            continue
        if folder and not model.get("folder", "").startswith(folder):
            continue
        if tag and tag not in model.get("tags", []):
            continue

        results.append(
            {
                "unique_id": uid,
                "name": model["name"],
                "description": model.get("description", ""),
                "materialization": model.get("materialization", ""),
                "schema": model.get("schema", ""),
                "folder": model.get("folder", ""),
                "tags": model.get("tags", []),
                "column_count": len(model.get("columns", [])),
                "has_description": bool(model.get("description")),
            }
        )

    return {"models": results, "count": len(results)}


def _get_model(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Get full detail for a single model."""
    identifier = params.get("name") or params.get("unique_id", "")

    # Search by unique_id first, then by name
    model = data["models"].get(identifier)
    if not model:
        for uid, m in data["models"].items():
            if m["name"] == identifier:
                model = m
                break

    if not model:
        return {"error": f"Model not found: {identifier}"}

    return {
        "unique_id": model["unique_id"],
        "name": model["name"],
        "description": model.get("description", ""),
        "schema": model.get("schema", ""),
        "database": model.get("database", ""),
        "materialization": model.get("materialization", ""),
        "tags": model.get("tags", []),
        "path": model.get("path", ""),
        "folder": model.get("folder", ""),
        "raw_sql": model.get("raw_sql", ""),
        "compiled_sql": model.get("compiled_sql", ""),
        "columns": model.get("columns", []),
        "depends_on": model.get("depends_on", []),
        "referenced_by": model.get("referenced_by", []),
        "sources_used": model.get("sources_used", []),
        "test_results": model.get("test_results", []),
        "last_run": model.get("last_run"),
        "catalog_stats": model.get("catalog_stats", {}),
    }


def _get_source(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Get detail for a single source."""
    identifier = params.get("name") or params.get("unique_id", "")

    source = data["sources"].get(identifier)
    if not source:
        for uid, s in data["sources"].items():
            # Match by "source_name.name" or just "name"
            full_name = f"{s.get('source_name', '')}.{s['name']}"
            if s["name"] == identifier or full_name == identifier:
                source = s
                break

    if not source:
        return {"error": f"Source not found: {identifier}"}

    return source


def _get_lineage(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Get upstream and downstream lineage for a model."""
    identifier = params.get("name") or params.get("unique_id", "")
    depth = params.get("depth", 100)
    direction = params.get("direction", "both")  # upstream | downstream | both

    # Find the model
    all_resources = {**data["models"], **data["sources"], **data["seeds"], **data["snapshots"]}
    target_uid = None

    if identifier in all_resources:
        target_uid = identifier
    else:
        for uid, r in all_resources.items():
            if r.get("name") == identifier:
                target_uid = uid
                break
            full_name = f"{r.get('source_name', '')}.{r.get('name', '')}"
            if full_name == identifier:
                target_uid = uid
                break

    if not target_uid:
        return {"error": f"Resource not found: {identifier}"}

    upstream: list[str] = []
    downstream: list[str] = []

    if direction in ("upstream", "both"):
        _collect_deps(target_uid, all_resources, upstream, depth, "depends_on")

    if direction in ("downstream", "both"):
        _collect_deps(target_uid, all_resources, downstream, depth, "referenced_by")

    def _summarize(uid: str) -> dict[str, Any]:
        r = all_resources.get(uid, {})
        return {
            "unique_id": uid,
            "name": r.get("name", uid.split(".")[-1]),
            "resource_type": uid.split(".")[0] if "." in uid else "unknown",
            "description": r.get("description", ""),
        }

    # Filter out test nodes and resources not in our data
    upstream = [u for u in upstream if u in all_resources and not u.startswith("test.")]
    downstream = [d for d in downstream if d in all_resources and not d.startswith("test.")]

    return {
        "target": target_uid,
        "upstream": [_summarize(u) for u in upstream],
        "downstream": [_summarize(d) for d in downstream],
    }


def _collect_deps(
    uid: str,
    resources: dict[str, Any],
    collected: list[str],
    max_depth: int,
    key: str,
    _depth: int = 0,
    _visited: set[str] | None = None,
) -> None:
    """Recursively collect dependencies in a given direction."""
    if _depth >= max_depth:
        return
    if _visited is None:
        _visited = {uid}

    resource = resources.get(uid, {})
    for dep in resource.get(key, []):
        if dep not in _visited:
            _visited.add(dep)
            collected.append(dep)
            _collect_deps(dep, resources, collected, max_depth, key, _depth + 1, _visited)


def _get_health(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Get project health score with breakdown."""
    return data["health"]


def _find_undocumented(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Find models and columns missing descriptions, sorted by downstream impact."""
    resource_type = params.get("resource_type", "model")  # model | column | both
    limit = params.get("limit", 50)

    undocumented_models: list[dict[str, Any]] = []
    undocumented_columns: list[dict[str, Any]] = []

    for uid, model in data["models"].items():
        if model.get("is_package", False):
            continue

        downstream_count = len(model.get("referenced_by", []))

        if resource_type in ("model", "both") and not model.get("description"):
            undocumented_models.append(
                {
                    "unique_id": uid,
                    "name": model["name"],
                    "folder": model.get("folder", ""),
                    "downstream_count": downstream_count,
                }
            )

        if resource_type in ("column", "both"):
            for col in model.get("columns", []):
                if not col.get("description"):
                    undocumented_columns.append(
                        {
                            "model": model["name"],
                            "column": col["name"],
                            "model_unique_id": uid,
                            "downstream_count": downstream_count,
                        }
                    )

    undocumented_models.sort(key=lambda x: x["downstream_count"], reverse=True)
    undocumented_columns.sort(key=lambda x: x["downstream_count"], reverse=True)

    return {
        "undocumented_models": undocumented_models[:limit],
        "undocumented_columns": undocumented_columns[:limit],
        "total_undocumented_models": len(undocumented_models),
        "total_undocumented_columns": len(undocumented_columns),
    }


def _find_untested(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Find models and columns missing tests."""
    limit = params.get("limit", 50)

    untested_models: list[dict[str, Any]] = []
    untested_columns: list[dict[str, Any]] = []

    for uid, model in data["models"].items():
        if model.get("is_package", False):
            continue

        downstream_count = len(model.get("referenced_by", []))
        test_results = model.get("test_results", [])

        if not test_results:
            untested_models.append(
                {
                    "unique_id": uid,
                    "name": model["name"],
                    "folder": model.get("folder", ""),
                    "downstream_count": downstream_count,
                }
            )

        # Find columns with no tests
        tested_columns = {
            t.get("column_name", "").lower() for t in test_results if t.get("column_name")
        }
        for col in model.get("columns", []):
            if col["name"].lower() not in tested_columns:
                untested_columns.append(
                    {
                        "model": model["name"],
                        "column": col["name"],
                        "model_unique_id": uid,
                        "downstream_count": downstream_count,
                    }
                )

    untested_models.sort(key=lambda x: x["downstream_count"], reverse=True)
    untested_columns.sort(key=lambda x: x["downstream_count"], reverse=True)

    return {
        "untested_models": untested_models[:limit],
        "untested_columns": untested_columns[:limit],
        "total_untested_models": len(untested_models),
        "total_untested_columns": len(untested_columns),
    }


def _search(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Search across models, sources, columns, and tags."""
    query = params.get("query", "").lower()
    limit = params.get("limit", 20)

    if not query:
        return {"error": "query parameter is required", "results": []}

    results: list[dict[str, Any]] = []

    all_resources = {
        **{uid: {**m, "_type": "model"} for uid, m in data["models"].items()},
        **{uid: {**s, "_type": "source"} for uid, s in data["sources"].items()},
        **{uid: {**s, "_type": "seed"} for uid, s in data["seeds"].items()},
        **{uid: {**s, "_type": "snapshot"} for uid, s in data["snapshots"].items()},
    }

    for uid, resource in all_resources.items():
        score = 0
        name = resource.get("name", "")
        description = resource.get("description", "")
        tags = resource.get("tags", [])
        columns = resource.get("columns", [])
        col_names = [c.get("name", "") for c in columns]

        # Score by match location
        if query == name.lower():
            score = 100  # exact name match
        elif query in name.lower():
            score = 80  # partial name match
        elif query in description.lower():
            score = 50  # description match
        elif any(query in t.lower() for t in tags):
            score = 40  # tag match
        elif any(query in c.lower() for c in col_names):
            score = 30  # column name match
        elif query in resource.get("raw_sql", "").lower():
            score = 10  # SQL match

        if score > 0:
            results.append(
                {
                    "unique_id": uid,
                    "name": name,
                    "resource_type": resource["_type"],
                    "description": description[:200],
                    "score": score,
                }
            )

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:limit], "total": len(results)}


def _get_column_info(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Get column details across all models where a column name appears."""
    column_name = params.get("column_name", "").lower()
    if not column_name:
        return {"error": "column_name parameter is required", "occurrences": []}

    occurrences: list[dict[str, Any]] = []

    for uid, model in data["models"].items():
        for col in model.get("columns", []):
            if col["name"].lower() == column_name:
                occurrences.append(
                    {
                        "model_unique_id": uid,
                        "model_name": model["name"],
                        "column_name": col["name"],
                        "data_type": col.get("data_type", ""),
                        "description": col.get("description", ""),
                        "tests": col.get("tests", []),
                    }
                )

    for uid, source in data["sources"].items():
        for col in source.get("columns", []):
            if col["name"].lower() == column_name:
                occurrences.append(
                    {
                        "source_unique_id": uid,
                        "source_name": f"{source.get('source_name', '')}.{source['name']}",
                        "column_name": col["name"],
                        "data_type": col.get("data_type", ""),
                        "description": col.get("description", ""),
                    }
                )

    return {"column_name": column_name, "occurrences": occurrences, "count": len(occurrences)}


# --- Tool Registry ---

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="list_models",
        description=(
            "List all dbt models in the project. Can filter by name pattern (glob), folder, or tag."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name_pattern": {
                    "type": "string",
                    "description": "Glob pattern to match model names (e.g. 'stg_*', '*orders*')",
                },
                "folder": {
                    "type": "string",
                    "description": "Filter by folder prefix (e.g. 'models/staging')",
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by tag",
                },
                "include_packages": {
                    "type": "boolean",
                    "description": "Include models from dbt packages (default: false)",
                    "default": False,
                },
            },
        },
        handler=_list_models,
    ),
    ToolDefinition(
        name="get_model",
        description=(
            "Get full detail for a specific dbt model including SQL, columns, "
            "tests, dependencies, and run status."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Model name (e.g. 'stg_orders')",
                },
                "unique_id": {
                    "type": "string",
                    "description": "Model unique_id (e.g. 'model.jaffle_shop.stg_orders')",
                },
            },
        },
        handler=_get_model,
    ),
    ToolDefinition(
        name="get_source",
        description="Get detail for a dbt source including columns and freshness status.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Source name ('raw_orders') or qualified name ('jaffle_shop.raw_orders')"
                    ),
                },
                "unique_id": {
                    "type": "string",
                    "description": "Source unique_id",
                },
            },
        },
        handler=_get_source,
    ),
    ToolDefinition(
        name="get_lineage",
        description=(
            "Get the upstream and/or downstream lineage for a model or source. "
            "Shows what feeds into a model and what depends on it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Resource name or unique_id",
                },
                "unique_id": {
                    "type": "string",
                    "description": "Resource unique_id",
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth to traverse (default: 100)",
                    "default": 100,
                },
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream", "both"],
                    "description": "Direction to traverse (default: both)",
                    "default": "both",
                },
            },
        },
        handler=_get_lineage,
    ),
    ToolDefinition(
        name="get_health",
        description=(
            "Get the project health score with per-category breakdown "
            "(documentation, testing, freshness, complexity, naming, orphans)."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=_get_health,
    ),
    ToolDefinition(
        name="find_undocumented",
        description=(
            "Find models and/or columns that are missing descriptions, "
            "sorted by downstream impact (most-depended-on first)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "enum": ["model", "column", "both"],
                    "description": "What to check (default: model)",
                    "default": "model",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default: 50)",
                    "default": 50,
                },
            },
        },
        handler=_find_undocumented,
    ),
    ToolDefinition(
        name="find_untested",
        description="Find models and columns that have no tests, sorted by downstream impact.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default: 50)",
                    "default": 50,
                },
            },
        },
        handler=_find_untested,
    ),
    ToolDefinition(
        name="search",
        description=(
            "Search across all models, sources, seeds, and snapshots by name, "
            "description, tags, column names, or SQL content."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default: 20)",
                    "default": 20,
                },
            },
            "required": ["query"],
        },
        handler=_search,
    ),
    ToolDefinition(
        name="get_column_info",
        description=(
            "Get information about a column across all models and sources where it appears. "
            "Useful for understanding a column's lineage and usage."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "column_name": {
                    "type": "string",
                    "description": "Column name to look up",
                },
            },
            "required": ["column_name"],
        },
        handler=_get_column_info,
    ),
]

TOOL_MAP: dict[str, ToolDefinition] = {t.name: t for t in TOOLS}
