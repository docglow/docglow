"""High-level column lineage analysis — ties together parsing and resolution."""

from __future__ import annotations

import logging
import re
from typing import Any

from docglow.lineage.column_parser import (
    ColumnDependency,
    build_schema_mapping,
    parse_column_lineage,
)
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

    column_lineage: dict[str, dict[str, list[dict[str, str]]]] = {}
    parse_failures = 0
    total_models = 0

    all_models = {**models, **seeds, **snapshots}

    for uid, data in all_models.items():
        sql = data.get("compiled_sql", "")
        if not sql:
            raw = data.get("raw_sql", "")
            if not raw:
                continue
            # Only fall back to raw SQL if it contains no Jinja templates
            if "{{" in raw or "{%" in raw:
                sql = strip_jinja(raw)
            else:
                sql = raw

        if not sql or not sql.strip():
            continue

        total_models += 1

        # Get known column names from catalog for SELECT * fallback
        known_columns = [col["name"] for col in data.get("columns", []) if col.get("name")]

        try:
            raw_lineage = parse_column_lineage(
                compiled_sql=sql,
                schema=schema,
                dialect=dialect,
                known_columns=known_columns or None,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Failed to parse column lineage for %s", uid)
            parse_failures += 1
            continue

        if not raw_lineage:
            continue

        model_lineage = _resolve_dependencies(raw_lineage, resolver)
        if model_lineage:
            column_lineage[uid] = model_lineage

    if parse_failures > 0:
        logger.warning(
            "Column lineage: %d/%d models could not be analyzed",
            parse_failures,
            total_models,
        )

    logger.info(
        "Column lineage: analyzed %d models, %d with column dependencies",
        total_models,
        len(column_lineage),
    )

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
    sql = _JINJA_GENERIC.sub("NULL", sql)
    sql = _JINJA_BLOCK.sub("", sql)
    return sql


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
