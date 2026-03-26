"""Lightweight SQL usage detection via sqlglot AST walk.

Detects how each column is used in a model's SQL: join keys, group by,
filters, aggregations, or select-only. Single parse per model, no lineage
trace needed.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def detect_sql_usage(
    compiled_sql: str,
    column_names: list[str],
    dialect: str | None = None,
) -> dict[str, set[str]]:
    """Detect SQL usage patterns for each column in a model.

    Args:
        compiled_sql: The compiled SQL string.
        column_names: List of known column names for the model.
        dialect: SQL dialect for parsing.

    Returns:
        Dict mapping column_name -> set of usage patterns.
        Patterns: "join_key", "group_by", "filtered", "aggregated", "selected_only"
    """
    if not compiled_sql or not compiled_sql.strip():
        return {}

    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return {}

    try:
        parsed = sqlglot.parse(compiled_sql, dialect=dialect)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to parse SQL for usage detection")
        return {}

    if not parsed or parsed[0] is None:
        return {}

    tree = parsed[0]

    # Build case-insensitive lookup
    name_lower = {n.lower() for n in column_names}
    usage: dict[str, set[str]] = {}

    def _add(col_name: str, pattern: str) -> None:
        lower = col_name.lower()
        if lower not in name_lower:
            return
        # Use the original-cased name from column_names
        canonical = next((n for n in column_names if n.lower() == lower), col_name)
        if canonical not in usage:
            usage[canonical] = set()
        usage[canonical].add(pattern)

    def _extract_column_names(node: Any) -> list[str]:
        """Extract column name strings from an expression subtree."""
        cols: list[str] = []
        for col in node.find_all(exp.Column):
            if col.name:
                cols.append(col.name)
        return cols

    # Walk JOIN conditions
    for join in tree.find_all(exp.Join):
        on_clause = join.find(exp.EQ)
        if on_clause:
            for col_name in _extract_column_names(on_clause):
                _add(col_name, "join_key")

    # Walk GROUP BY
    for group in tree.find_all(exp.Group):
        for col_name in _extract_column_names(group):
            _add(col_name, "group_by")

    # Walk WHERE / HAVING
    for where in tree.find_all(exp.Where):
        for col_name in _extract_column_names(where):
            _add(col_name, "filtered")
    for having in tree.find_all(exp.Having):
        for col_name in _extract_column_names(having):
            _add(col_name, "filtered")

    # Walk aggregate functions
    for agg in tree.find_all(exp.AggFunc):
        for col_name in _extract_column_names(agg):
            _add(col_name, "aggregated")

    # Mark columns that appear in SQL but have no other usage as "selected_only"
    for name in column_names:
        if name not in usage:
            usage[name] = {"selected_only"}

    return usage
