"""High-level column lineage analysis — ties together parsing and resolution."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import os
import re
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
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


@dataclass
class _ModelLineageResult:
    """Result of analyzing column lineage for a single model."""

    uid: str
    lineage: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    cache_entry: dict[str, Any] = field(default_factory=dict)
    failure: dict[str, str] | None = None
    cached: bool = False
    skipped: bool = False


def _compute_depth_waves(
    all_models: dict[str, dict[str, Any]],
) -> list[list[str]]:
    """Compute topological depth waves for parallel processing.

    Returns a list of waves, where each wave contains model UIDs that can be
    processed in parallel (all their upstream dependencies are in earlier waves).

    Models with no in-set dependencies are in wave 0. Models whose dependencies
    are all outside the set (e.g. sources) are also in wave 0.
    """
    model_uids = set(all_models.keys())

    # Build in-degree map: only count dependencies that are within our model set
    in_degree: dict[str, int] = {}
    dependents: dict[str, list[str]] = {uid: [] for uid in model_uids}

    for uid, data in all_models.items():
        deps_in_set = [d for d in data.get("depends_on", []) if d in model_uids]
        in_degree[uid] = len(deps_in_set)
        for dep in deps_in_set:
            dependents[dep].append(uid)

    # BFS from roots (in-degree 0) to assign depth
    waves: list[list[str]] = []
    current_wave = [uid for uid, deg in in_degree.items() if deg == 0]

    while current_wave:
        waves.append(current_wave)
        next_wave: list[str] = []
        for uid in current_wave:
            for dependent in dependents[uid]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_wave.append(dependent)
        current_wave = next_wave

    # Any remaining models (cycles) go in a final wave
    processed = {uid for wave in waves for uid in wave}
    remaining = [uid for uid in model_uids if uid not in processed]
    if remaining:
        waves.append(remaining)

    return waves


# Module-level state for worker processes (set by _init_worker)
_worker_schema: dict[str, dict[str, str]] = {}
_worker_resolver: TableResolver | None = None
_worker_dialect: str | None = None


def _init_worker(
    schema: dict[str, dict[str, str]],
    resolver: TableResolver,
    dialect: str | None,
) -> None:
    """Initialize shared read-only state in each worker process."""
    global _worker_schema, _worker_resolver, _worker_dialect  # noqa: PLW0603
    _worker_schema = schema
    _worker_resolver = resolver
    _worker_dialect = dialect


def _analyze_model_in_worker(
    uid: str,
    data: dict[str, Any],
    cached_entry: dict[str, Any] | None,
) -> _ModelLineageResult:
    """Wrapper for _analyze_single_model that uses process-local shared state."""
    return _analyze_single_model(
        uid=uid,
        data=data,
        schema=_worker_schema,
        resolver=_worker_resolver,  # type: ignore[arg-type]
        dialect=_worker_dialect,
        cached_entry=cached_entry,
    )


def _analyze_single_model(
    uid: str,
    data: dict[str, Any],
    schema: dict[str, dict[str, str]],
    resolver: TableResolver,
    dialect: str | None,
    cached_entry: dict[str, Any] | None,
) -> _ModelLineageResult:
    """Analyze column lineage for a single model. Pure function, no side effects.

    All inputs are read-only. Returns a result struct that the caller merges
    into shared state.
    """
    sql = data.get("compiled_sql", "")
    if not sql:
        raw = data.get("raw_sql", "")
        if not raw:
            return _ModelLineageResult(uid=uid, skipped=True)
        if "{{" in raw or "{%" in raw:
            sql = strip_jinja(raw)
        else:
            sql = raw

    if not sql or not sql.strip():
        return _ModelLineageResult(uid=uid, skipped=True)

    sql_hash = _hash_sql(sql)

    # Check cache
    if cached_entry and cached_entry.get("sql_hash") == sql_hash:
        cached_lineage = cached_entry.get("lineage")
        return _ModelLineageResult(
            uid=uid,
            lineage=cached_lineage or {},
            cached=True,
        )

    known_columns = [col["name"] for col in data.get("columns", []) if col.get("name")]

    try:
        raw_lineage = parse_column_lineage(
            compiled_sql=sql,
            schema=schema,
            dialect=dialect,
            known_columns=known_columns or None,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("Failed to parse column lineage for %s: %s", uid, e)
        return _ModelLineageResult(
            uid=uid,
            cache_entry={"sql_hash": sql_hash, "lineage": {}},
            failure={
                "model": uid,
                "name": data.get("name", ""),
                "error": str(e),
            },
        )

    if not raw_lineage:
        failure = None
        if known_columns:
            failure = {
                "model": uid,
                "name": data.get("name", ""),
                "error": f"No columns traced ({len(known_columns)} columns in schema)",
            }
        return _ModelLineageResult(
            uid=uid,
            cache_entry={"sql_hash": sql_hash, "lineage": {}},
            failure=failure,
        )

    model_lineage = _resolve_dependencies(raw_lineage, resolver)
    cache_entry_out = {"sql_hash": sql_hash, "lineage": model_lineage}

    # Track partially traced models
    failure = None
    if known_columns and len(model_lineage) < len(known_columns):
        traced = set(model_lineage.keys())
        missed = [c for c in known_columns if c not in traced]
        if missed:
            failure = {
                "model": uid,
                "name": data.get("name", ""),
                "error": f"Partial: {len(missed)}/{len(known_columns)} columns not traced",
                "columns": ", ".join(missed[:20]),
            }

    return _ModelLineageResult(
        uid=uid,
        lineage=model_lineage,
        cache_entry=cache_entry_out,
        failure=failure,
    )


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
    max_workers: int | None = None,
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Analyze column-level lineage for all models.

    Uses compiled_sql when available, falls back to raw_sql with Jinja
    stripped for models that haven't been compiled.

    When the model count exceeds the parallel threshold, models are processed
    concurrently using a process pool (bypasses the GIL for CPU-bound SQLGlot
    parsing). Below the threshold or with max_workers=1, models run sequentially
    in topological order.

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
        max_workers: Max parallel workers for lineage parsing.
            Defaults to min(8, cpu_count). Set to 1 for sequential.

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

    # Subset filtering: include cached results for models outside subset
    if subset is not None:
        for uid in all_models:
            if uid not in subset:
                cached_entry = cache.get(uid)
                if cached_entry and cached_entry.get("lineage"):
                    column_lineage[uid] = cached_entry["lineage"]

    # Determine which models to analyze
    uids_to_analyze = (
        [uid for uid in all_models if uid in subset]
        if subset is not None
        else list(all_models.keys())
    )
    analyzable_count = len(uids_to_analyze)

    # Process pool has meaningful startup cost (fork + serialize schema/resolver),
    # so only use it when there are enough models to amortize the overhead.
    parallel_threshold = 20
    workers = max_workers if max_workers is not None else min(8, os.cpu_count() or 1)
    use_parallel = workers > 1 and analyzable_count >= parallel_threshold

    analyzed_count = 0

    if use_parallel:
        logger.info(
            "Column lineage: %d models, %d workers",
            analyzable_count,
            workers,
        )

        # Submit all models to the pool at once. Each model's parsing is
        # independent (uses only its own SQL + the shared schema/resolver).
        # Note: each model's data dict is pickled per submit() call — the
        # compiled_sql strings dominate IPC cost for large models.
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(schema, resolver, dialect),
        ) as pool:
            futures = {
                pool.submit(
                    _analyze_model_in_worker,
                    uid,
                    all_models[uid],
                    cache.get(uid),
                ): uid
                for uid in uids_to_analyze
            }

            for future in as_completed(futures):
                result = future.result()
                analyzed_count += 1
                _merge_result(
                    result,
                    all_models,
                    column_lineage,
                    cache,
                    failure_details,
                    analyzed_count,
                    analyzable_count,
                )
                if not result.skipped:
                    total_models += 1
                    if result.cached:
                        cache_hits += 1
                    elif result.failure:
                        parse_failures += 1
    else:
        # Sequential: process in topological order (upstream before downstream)
        waves = _compute_depth_waves({uid: all_models[uid] for uid in uids_to_analyze})
        for wave_uids in waves:
            for uid in wave_uids:
                result = _analyze_single_model(
                    uid=uid,
                    data=all_models[uid],
                    schema=schema,
                    resolver=resolver,
                    dialect=dialect,
                    cached_entry=cache.get(uid),
                )
                analyzed_count += 1
                _merge_result(
                    result,
                    all_models,
                    column_lineage,
                    cache,
                    failure_details,
                    analyzed_count,
                    analyzable_count,
                )
                if not result.skipped:
                    total_models += 1
                    if result.cached:
                        cache_hits += 1
                    elif result.failure:
                        parse_failures += 1

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


def _merge_result(
    result: _ModelLineageResult,
    all_models: dict[str, dict[str, Any]],
    column_lineage: dict[str, dict[str, list[dict[str, str]]]],
    cache: dict[str, Any],
    failure_details: list[dict[str, str]],
    analyzed_count: int,
    analyzable_count: int,
) -> None:
    """Merge a single model's lineage result into shared state.

    Called sequentially (after future.result() in parallel mode, or directly
    in sequential mode) so no locking is needed.
    """
    if result.skipped:
        return

    if result.cached:
        if result.lineage:
            column_lineage[result.uid] = result.lineage
        return

    model_name = all_models[result.uid].get("name", result.uid.split(".")[-1])
    logger.info(
        "Column lineage: analyzed %s (%d/%d)",
        model_name,
        analyzed_count,
        analyzable_count,
    )

    if result.cache_entry:
        cache[result.uid] = result.cache_entry
    if result.lineage:
        column_lineage[result.uid] = result.lineage
    if result.failure:
        failure_details.append(result.failure)


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

    # Remove meta key and migrate legacy "direct" → "passthrough"
    cache = {k: v for k, v in raw.items() if k != _CACHE_VERSION_KEY}
    _migrate_direct_to_passthrough(cache)
    return cache


def _migrate_direct_to_passthrough(cache: dict[str, Any]) -> None:
    """Migrate legacy 'direct' transformation values to 'passthrough'.

    Prior to the transformation reclassification (DOC-76), simple column
    references were labelled 'direct'. This rewrites them in-place so
    downstream code only sees the new vocabulary.
    """
    for entry in cache.values():
        if not isinstance(entry, dict):
            continue
        lineage = entry.get("lineage")
        if not isinstance(lineage, dict):
            continue
        for deps in lineage.values():
            if not isinstance(deps, list):
                continue
            for dep in deps:
                if isinstance(dep, dict) and dep.get("transformation") == "direct":
                    dep["transformation"] = "passthrough"


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
