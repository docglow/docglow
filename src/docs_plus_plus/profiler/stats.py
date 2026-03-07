"""Parse profiling query results into structured profile dicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from docs_plus_plus.profiler.queries import ColumnSpec


@dataclass(frozen=True)
class ColumnProfile:
    row_count: int
    null_count: int
    null_rate: float
    distinct_count: int
    distinct_rate: float
    is_unique: bool
    min: Any | None = None
    max: Any | None = None
    mean: float | None = None
    median: float | None = None
    stddev: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    avg_length: float | None = None
    top_values: list[dict[str, Any]] | None = None


def parse_stats_row(
    row: dict[str, Any],
    columns: list[ColumnSpec],
) -> dict[str, dict[str, Any]]:
    """Parse a stats query result row into per-column profile dicts.

    Args:
        row: Dict of column_name -> value from the stats query result.
        columns: The ColumnSpec list used to generate the query.

    Returns:
        Dict mapping column name -> profile dict.
    """
    row_count = int(row.get("_row_count", 0))
    profiles: dict[str, dict[str, Any]] = {}

    for col in columns:
        prefix = f"{col.name}__"

        non_null = _get_int(row, f"{prefix}non_null_count", 0)
        null_count = row_count - non_null
        distinct = _get_int(row, f"{prefix}distinct_count", 0)

        profile: dict[str, Any] = {
            "row_count": row_count,
            "null_count": null_count,
            "null_rate": round(null_count / row_count, 4) if row_count > 0 else 0.0,
            "distinct_count": distinct,
            "distinct_rate": round(distinct / non_null, 4) if non_null > 0 else 0.0,
            "is_unique": distinct == non_null and non_null > 0,
        }

        if col.category == "numeric":
            profile["min"] = _get_numeric(row, f"{prefix}min")
            profile["max"] = _get_numeric(row, f"{prefix}max")
            profile["mean"] = _get_float(row, f"{prefix}mean")
            profile["median"] = _get_float(row, f"{prefix}median")
            profile["stddev"] = _get_float(row, f"{prefix}stddev")

        elif col.category == "date":
            profile["min"] = _get_str(row, f"{prefix}min")
            profile["max"] = _get_str(row, f"{prefix}max")

        elif col.category == "string":
            profile["min_length"] = _get_int(row, f"{prefix}min_length")
            profile["max_length"] = _get_int(row, f"{prefix}max_length")
            profile["avg_length"] = _get_float(row, f"{prefix}avg_length")

        profiles[col.name] = profile

    return profiles


def parse_top_values_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse top values query results into a list of {value, frequency} dicts."""
    return [
        {"value": str(r.get("value", "")), "frequency": int(r.get("frequency", 0))}
        for r in rows
    ]


def _get_int(row: dict[str, Any], key: str, default: int = 0) -> int:
    val = row.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_float(row: dict[str, Any], key: str) -> float | None:
    val = row.get(key)
    if val is None:
        return None
    try:
        return round(float(val), 6)
    except (ValueError, TypeError):
        return None


def _get_numeric(row: dict[str, Any], key: str) -> Any | None:
    val = row.get(key)
    if val is None:
        return None
    # Try int first, then float
    try:
        f = float(val)
        if f == int(f) and abs(f) < 2**53:
            return int(f)
        return round(f, 6)
    except (ValueError, TypeError):
        return str(val)


def _get_str(row: dict[str, Any], key: str) -> str | None:
    val = row.get(key)
    if val is None:
        return None
    return str(val)
