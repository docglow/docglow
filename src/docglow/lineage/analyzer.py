"""High-level column lineage analysis — ties together parsing and resolution."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import re
from collections import deque
from pathlib import Path
from typing import Any

from docglow import __version__
from docglow.lineage.column_parser import (
    ColumnDependency,
    build_schema_mapping,
    parse_column_lineage,
)
from docglow.lineage.macro_expander import expand_macros
from docglow.lineage.table_resolver import TableResolver

logger = logging.getLogger(__name__)

# Patterns for stripping Jinja from raw dbt SQL
_JINJA_CONFIG = re.compile(r"\{\{\s*config\s*\(.*?\)\s*\}\}", re.DOTALL)
_JINJA_REF = re.compile(r"\{\{\s*ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_JINJA_SOURCE = re.compile(
    r"\{\{\s*source\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)
_JINJA_GENERIC = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_JINJA_BLOCK = re.compile(r"\{%.*?%\}", re.DOTALL)


def analyze_column_lineage(
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    dialect: str | None = None,
    manifest_nodes: dict[str, Any] | None = None,
    manifest_sources: dict[str, Any] | None = None,
    cache_path: Path | None = None,
    subset: set[str] | None = None,
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Analyze column-level lineage for all models.

    Uses compiled_sql when available, falls back to raw_sql with Jinja
    stripped for models that haven't been compiled.

    Args:
        models: Transformed model data from build_docglow_data.
        sources: Transformed source data.
        seeds: Transformed seed data.
        snapshots: Transformed snapshot data.
        dialect: SQL dialect for parsing.
        manifest_nodes: Raw manifest nodes (for relation_name resolution).
        manifest_sources: Raw manifest sources (for relation_name resolution).
        cache_path: Path to the column lineage cache file.
        subset: If provided, only analyze these model unique_ids.
            Models outside the subset still have their cached results included.

    Returns:
        Dict of {model_unique_id: {column_name: [dependency_dicts]}}.
    """
    resolver = TableResolver(
        models=models,
        sources=sources,
        seeds=seeds,
        snapshots=snapshots,
        manifest_nodes=manifest_nodes,
        manifest_sources=manifest_sources,
    )
    schema = build_schema_mapping(models, sources)

    # Load cache if available
    cache = _load_cache(cache_path, dialect)
    cache_hits = 0

    column_lineage: dict[str, dict[str, list[dict[str, str]]]] = {}
    parse_failures = 0
    total_models = 0
    failure_details: list[dict[str, str]] = []

    all_models = {**models, **seeds, **snapshots}

    if subset is not None:
        logger.info(
            "Column lineage: subset selection active (%d/%d models)",
            len(subset & set(all_models.keys())),
            len(all_models),
        )

    for uid, data in all_models.items():
        # Subset filtering: skip models outside the subset but include cached results
        if subset is not None and uid not in subset:
            cached_entry = cache.get(uid)
            if cached_entry and cached_entry.get("lineage"):
                column_lineage[uid] = cached_entry["lineage"]
            continue

        sql = data.get("compiled_sql", "")
        if not sql:
            raw = data.get("raw_sql", "")
            if not raw:
                continue
            if "{{" in raw or "{%" in raw:
                sql = strip_jinja(raw)
            else:
                sql = raw

        if not sql or not sql.strip():
            continue

        total_models += 1
        sql_hash = _hash_sql(sql)

        # Check cache
        cached_entry = cache.get(uid)
        if cached_entry and cached_entry.get("sql_hash") == sql_hash:
            cached_lineage = cached_entry.get("lineage")
            if cached_lineage:
                column_lineage[uid] = cached_lineage
            cache_hits += 1
            continue

        known_columns = [col["name"] for col in data.get("columns", []) if col.get("name")]

        try:
            raw_lineage = parse_column_lineage(
                compiled_sql=sql,
                schema=schema,
                dialect=dialect,
                known_columns=known_columns or None,
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to parse column lineage for %s", uid)
            parse_failures += 1
            failure_details.append(
                {
                    "model": uid,
                    "name": data.get("name", ""),
                    "error": str(e),
                }
            )
            cache[uid] = {"sql_hash": sql_hash, "lineage": {}}
            continue

        if not raw_lineage:
            if known_columns:
                failure_details.append(
                    {
                        "model": uid,
                        "name": data.get("name", ""),
                        "error": f"No columns traced ({len(known_columns)} columns in schema)",
                    }
                )
            cache[uid] = {"sql_hash": sql_hash, "lineage": {}}
            continue

        model_lineage = _resolve_dependencies(raw_lineage, resolver)
        cache[uid] = {"sql_hash": sql_hash, "lineage": model_lineage}
        if model_lineage:
            column_lineage[uid] = model_lineage

        # Track partially traced models
        if known_columns and len(model_lineage) < len(known_columns):
            traced = set(model_lineage.keys())
            missed = [c for c in known_columns if c not in traced]
            if missed:
                failure_details.append(
                    {
                        "model": uid,
                        "name": data.get("name", ""),
                        "error": f"Partial: {len(missed)}/{len(known_columns)} columns not traced",
                        "columns": ", ".join(missed[:20]),
                    }
                )

    if parse_failures > 0:
        logger.warning(
            "Column lineage: %d/%d models could not be analyzed",
            parse_failures,
            total_models,
        )

    logger.info(
        "Column lineage: analyzed %d models (%d cached), %d with column dependencies",
        total_models,
        cache_hits,
        len(column_lineage),
    )

    # Save updated cache
    _save_cache(cache_path, cache, dialect)

    # Write failure report if there were issues
    if failure_details:
        _write_failure_report(failure_details, cache_path)

    return column_lineage


def strip_jinja(raw_sql: str) -> str:
    """Strip Jinja templating from raw dbt SQL to make it parseable.

    - {{ config(...) }} -> removed entirely
    - {{ ref('model_name') }} -> model_name
    - {{ source('source', 'table') }} -> source.table
    - {{ other_macro(...) }} -> NULL (placeholder to keep SQL valid)
    - {% ... %} blocks -> removed
    """
    sql = _JINJA_CONFIG.sub("", raw_sql)
    sql = _JINJA_REF.sub(r"\1", sql)
    sql = _JINJA_SOURCE.sub(r"\1.\2", sql)
    sql = expand_macros(sql)
    sql = _JINJA_GENERIC.sub("NULL", sql)
    sql = _JINJA_BLOCK.sub("", sql)
    return sql


def compute_column_lineage_subset(
    pattern: str,
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    max_depth: int | None = None,
) -> set[str]:
    """Compute the set of model unique_ids to analyze for column lineage.

    Supports the same ``+name`` / ``name+`` direction syntax as ``--select``:
      - ``fct_orders`` or ``+fct_orders`` — the model and its upstream dependencies
      - ``fct_orders+`` — the model and its downstream consumers
      - ``+fct_orders+`` — both directions

    Glob patterns are supported (e.g. ``fct_*``).

    Args:
        pattern: Model name pattern with optional direction operators.
        models: Transformed model data.
        sources: Transformed source data.
        seeds: Transformed seed data.
        snapshots: Transformed snapshot data.
        max_depth: Maximum hops to traverse. None means unlimited.

    Returns:
        Set of unique_ids to include in column lineage analysis.
    """
    include_upstream = not pattern.endswith("+") or pattern.startswith("+")
    include_downstream = pattern.endswith("+")

    # Default (no + at all) is upstream only
    if "+" not in pattern:
        include_upstream = True
        include_downstream = False

    clean = pattern.strip("+")

    all_resources = {**models, **seeds, **snapshots}

    # Match seed models by name, folder, or path
    matched: set[str] = set()
    for uid, data in all_resources.items():
        name = data.get("name", "")
        folder = data.get("folder", "")
        path = data.get("path", "")
        if (
            fnmatch.fnmatch(name, clean)
            or fnmatch.fnmatch(folder, clean)
            or fnmatch.fnmatch(path, clean)
        ):
            matched.add(uid)

    if not matched:
        logger.warning("Column lineage subset: no models matched pattern '%s'", clean)
        return set()

    # BFS walk
    result: set[str] = set(matched)

    if include_upstream:
        _bfs_walk(matched, all_resources, sources, result, "depends_on", max_depth)

    if include_downstream:
        _bfs_walk(matched, all_resources, sources, result, "referenced_by", max_depth)

    logger.info(
        "Column lineage subset: '%s' matched %d seed models, %d total after traversal",
        pattern,
        len(matched),
        len(result),
    )

    return result


def _bfs_walk(
    seed_ids: set[str],
    all_resources: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    result: set[str],
    key: str,
    max_depth: int | None,
) -> None:
    """BFS walk through the dependency graph in a given direction."""
    queue: deque[tuple[str, int]] = deque((uid, 0) for uid in seed_ids)

    while queue:
        uid, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue

        # Get neighbors from model data or source data
        resource = all_resources.get(uid) or sources.get(uid)
        if not resource:
            continue

        for neighbor in resource.get(key, []):
            if neighbor not in result:
                result.add(neighbor)
                queue.append((neighbor, depth + 1))


def _resolve_dependencies(
    raw_lineage: dict[str, list[ColumnDependency]],
    resolver: TableResolver,
) -> dict[str, list[dict[str, str]]]:
    """Resolve table references in parsed lineage to dbt unique_ids."""
    resolved: dict[str, list[dict[str, str]]] = {}

    for col_name, deps in raw_lineage.items():
        resolved_deps: list[dict[str, str]] = []
        for dep in deps:
            source_model = resolver.resolve(dep.source_table)
            if source_model is None:
                # Unresolvable — could be a CTE or external table
                continue

            resolved_deps.append(
                {
                    "source_model": source_model,
                    "source_column": dep.source_column,
                    "transformation": dep.transformation,
                }
            )

        if resolved_deps:
            resolved[col_name] = resolved_deps

    return resolved


def _hash_sql(sql: str) -> str:
    """Compute a stable hash of SQL text for cache keying."""
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


_CACHE_VERSION_KEY = "__cache_meta__"


def _load_cache(
    cache_path: Path | None,
    dialect: str | None,
) -> dict[str, Any]:
    """Load the column lineage cache from disk. Returns empty dict on any error."""
    if not cache_path or not cache_path.exists():
        return {}

    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.debug("Column lineage cache is invalid, starting fresh")
        return {}

    if not isinstance(raw, dict):
        return {}

    # Invalidate if version or dialect changed
    meta = raw.get(_CACHE_VERSION_KEY, {})
    if meta.get("docglow_version") != __version__ or meta.get("dialect") != dialect:
        logger.debug("Column lineage cache invalidated (version/dialect change)")
        return {}

    # Remove meta key before returning
    return {k: v for k, v in raw.items() if k != _CACHE_VERSION_KEY}


def _save_cache(
    cache_path: Path | None,
    cache: dict[str, Any],
    dialect: str | None,
) -> None:
    """Save the column lineage cache to disk."""
    if not cache_path:
        return

    data = {
        _CACHE_VERSION_KEY: {
            "docglow_version": __version__,
            "dialect": dialect,
        },
        **cache,
    }

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    except OSError:
        logger.debug("Failed to write column lineage cache")


def _write_failure_report(
    failures: list[dict[str, str]],
    cache_path: Path | None,
) -> None:
    """Write a column lineage failure report alongside the cache file."""
    report_path = Path(".docglow-column-lineage-failures.log")
    if cache_path:
        report_path = cache_path.parent / ".docglow-column-lineage-failures.log"

    lines = [
        "# Column Lineage — Failure Report",
        f"# {len(failures)} models with issues",
        "#",
        "# Common causes:",
        "#   - Snowflake variant access syntax (obj:key::type)",
        "#   - Complex macros that couldn't be expanded to SQL",
        "#   - Columns missing from catalog (run `dbt docs generate`)",
        "",
    ]

    for entry in sorted(failures, key=lambda x: x.get("name", "")):
        lines.append(f"{entry.get('name', '')}  ({entry.get('model', '')})")
        lines.append(f"  {entry.get('error', 'Unknown error')}")
        if entry.get("columns"):
            lines.append(f"  Columns: {entry['columns']}")
        lines.append("")

    try:
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(
            "Column lineage: %d models with issues — see %s",
            len(failures),
            report_path,
        )
    except OSError:
        logger.debug("Failed to write column lineage failure report")
