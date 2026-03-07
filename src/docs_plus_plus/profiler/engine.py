"""Profiling query engine — executes profiling queries against the warehouse."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from docs_plus_plus.profiler.cache import (
    get_cached_profiles,
    is_cached,
    load_cache,
    save_cache,
    update_cache,
)
from docs_plus_plus.profiler.queries import (
    build_column_specs,
    build_stats_query,
    build_top_values_query,
)
from docs_plus_plus.profiler.stats import parse_stats_row, parse_top_values_rows

logger = logging.getLogger(__name__)


class ProfilerError(Exception):
    """Raised when profiling fails."""


def _get_connection_url(adapter: str, connection_params: dict[str, Any]) -> str:
    """Build a SQLAlchemy connection URL from adapter type and params."""
    if adapter == "duckdb":
        path = connection_params.get("path", ":memory:")
        return f"duckdb:///{path}"
    if adapter in ("postgres", "postgresql"):
        host = connection_params.get("host", "localhost")
        port = connection_params.get("port", 5432)
        user = connection_params.get("user", "")
        password = connection_params.get("password", "")
        dbname = connection_params.get("dbname", connection_params.get("database", ""))
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    if adapter == "snowflake":
        account = connection_params.get("account", "")
        user = connection_params.get("user", "")
        password = connection_params.get("password", "")
        database = connection_params.get("database", "")
        warehouse = connection_params.get("warehouse", "")
        return (
            f"snowflake://{user}:{password}@{account}/{database}"
            f"?warehouse={warehouse}"
        )
    raise ProfilerError(f"Unsupported adapter: {adapter}")


def profile_models(
    models: dict[str, dict[str, Any]],
    adapter: str,
    connection_params: dict[str, Any],
    *,
    sample_size: int | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    top_values_threshold: int = 50,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Profile all models and return per-model, per-column profile data.

    Args:
        models: Dict of model_id -> model data dict.
        adapter: Database adapter type (duckdb, postgres, snowflake).
        connection_params: Connection parameters for the adapter.
        sample_size: Max rows to sample per model (None = full table).
        cache_dir: Directory to store/load profile cache.
        use_cache: Whether to use caching.
        top_values_threshold: Max distinct values to collect top_values for.

    Returns:
        Dict mapping model_id -> column_name -> profile dict.
    """
    try:
        from sqlalchemy import create_engine, text
    except ImportError as e:
        raise ProfilerError(
            "SQLAlchemy is required for profiling. "
            "Install with: pip install docs-plus-plus[profiling]"
        ) from e

    cache: dict[str, Any] = {}
    if cache_dir and use_cache:
        cache = load_cache(cache_dir)

    url = _get_connection_url(adapter, connection_params)
    engine = create_engine(url)

    all_profiles: dict[str, dict[str, dict[str, Any]]] = {}
    profiled_count = 0
    cached_count = 0

    try:
        with engine.connect() as conn:
            for model_id, model in models.items():
                columns = model.get("columns", [])
                if not columns:
                    continue

                row_count = None
                catalog_stats = model.get("catalog_stats", {})
                if catalog_stats:
                    row_count = catalog_stats.get("row_count")

                # Check cache
                if use_cache and is_cached(cache, model_id, columns, row_count):
                    cached_profiles = get_cached_profiles(cache, model_id)
                    if cached_profiles is not None:
                        all_profiles[model_id] = cached_profiles
                        cached_count += 1
                        continue

                schema = model.get("schema", "")
                table_name = model.get("name", "")
                materialization = model.get("materialization", "")

                # Skip ephemeral models — they don't exist as tables
                if materialization == "ephemeral":
                    continue

                column_specs = build_column_specs(columns)

                # Build and execute stats query
                stats_sql = build_stats_query(
                    schema, table_name, column_specs,
                    adapter=adapter, sample_size=sample_size,
                )

                try:
                    logger.debug("Profiling %s.%s (%d columns)", schema, table_name, len(column_specs))
                    result = conn.execute(text(stats_sql))
                    row = result.mappings().fetchone()
                    if row is None:
                        logger.warning("No results for %s — skipping", model_id)
                        continue

                    profiles = parse_stats_row(dict(row), column_specs)

                    # Fetch top values for low-cardinality columns
                    for col_spec in column_specs:
                        col_profile = profiles.get(col_spec.name, {})
                        distinct = col_profile.get("distinct_count", 0)
                        if 0 < distinct <= top_values_threshold and col_spec.category in ("string", "numeric", "boolean"):
                            tv_sql = build_top_values_query(
                                schema, table_name, col_spec.name,
                                adapter=adapter,
                            )
                            try:
                                tv_result = conn.execute(text(tv_sql))
                                tv_rows = [dict(r) for r in tv_result.mappings()]
                                col_profile["top_values"] = parse_top_values_rows(tv_rows)
                            except Exception as e:
                                logger.debug("Top values query failed for %s.%s: %s", table_name, col_spec.name, e)

                    all_profiles[model_id] = profiles
                    profiled_count += 1

                    # Update cache
                    if cache_dir and use_cache:
                        cache = update_cache(cache, model_id, columns, row_count, profiles)

                except Exception as e:
                    logger.warning("Failed to profile %s: %s", model_id, e)
                    continue

    finally:
        engine.dispose()

    # Save cache
    if cache_dir and use_cache and profiled_count > 0:
        save_cache(cache_dir, cache)

    logger.info(
        "Profiling complete: %d profiled, %d cached, %d total",
        profiled_count, cached_count, profiled_count + cached_count,
    )
    return all_profiles


def apply_profiles(
    models: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Return new models dict with profile data applied to columns.

    Does not mutate the input models dict.
    """
    result: dict[str, dict[str, Any]] = {}
    for model_id, model in models.items():
        model_profiles = profiles.get(model_id, {})
        if not model_profiles:
            result[model_id] = model
            continue

        new_columns = [
            {**col, "profile": model_profiles.get(col["name"])}
            for col in model.get("columns", [])
        ]
        result[model_id] = {**model, "columns": new_columns}

    return result
