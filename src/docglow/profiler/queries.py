"""SQL query templates for column profiling by adapter type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    data_type: str
    category: str  # "numeric", "string", "date", "boolean", "other"


def classify_column(data_type: str) -> str:
    """Classify a column data type into a profiling category."""
    upper = data_type.upper().strip()
    if not upper:
        return "other"

    numeric_types = {
        "INTEGER",
        "INT",
        "BIGINT",
        "SMALLINT",
        "TINYINT",
        "FLOAT",
        "DOUBLE",
        "DECIMAL",
        "NUMBER",
        "NUMERIC",
        "REAL",
        "INT2",
        "INT4",
        "INT8",
        "FLOAT4",
        "FLOAT8",
        "HUGEINT",
        "UBIGINT",
        "UINTEGER",
        "USMALLINT",
        "UTINYINT",
    }
    date_types = {
        "DATE",
        "TIMESTAMP",
        "DATETIME",
        "TIMESTAMPTZ",
        "TIMESTAMP_NTZ",
        "TIMESTAMP_TZ",
        "TIMESTAMP_LTZ",
        "TIMESTAMP WITH TIME ZONE",
        "TIMESTAMP WITHOUT TIME ZONE",
    }
    string_types = {
        "VARCHAR",
        "TEXT",
        "STRING",
        "CHAR",
        "CHARACTER VARYING",
        "NVARCHAR",
        "NCHAR",
        "CLOB",
        "BPCHAR",
        "NAME",
    }
    boolean_types = {"BOOLEAN", "BOOL"}

    # Check exact match first
    base = upper.split("(")[0].strip()
    if base in numeric_types:
        return "numeric"
    if base in date_types:
        return "date"
    if base in string_types:
        return "string"
    if base in boolean_types:
        return "boolean"

    # Fuzzy matching for types with parameters
    if any(t in upper for t in ("INT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "NUMBER")):
        return "numeric"
    if any(t in upper for t in ("CHAR", "TEXT", "STRING", "VARCHAR")):
        return "string"
    if "TIMESTAMP" in upper or "DATE" in upper:
        return "date"
    if "BOOL" in upper:
        return "boolean"

    return "other"


def build_column_specs(columns: list[dict[str, Any]]) -> list[ColumnSpec]:
    """Build ColumnSpec list from column dicts."""
    return [
        ColumnSpec(
            name=col["name"],
            data_type=col.get("data_type", ""),
            category=classify_column(col.get("data_type", "")),
        )
        for col in columns
    ]


def _quote(name: str, adapter: str) -> str:
    """Quote a column name for the given adapter.

    Validates the identifier and escapes embedded quotes to prevent SQL injection.
    """
    if "\x00" in name:
        raise ValueError(f"Invalid identifier: contains null byte: {name!r}")

    if adapter == "bigquery":
        escaped = name.replace("`", "``")
        return f"`{escaped}`"
    # postgres, duckdb, snowflake — use double-quoted identifiers
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def build_stats_query(
    schema: str,
    table_name: str,
    columns: list[ColumnSpec],
    adapter: str = "duckdb",
    sample_size: int | None = None,
) -> str:
    """Build a single SQL query that profiles all columns in one pass."""
    q = _quote
    parts: list[str] = ["SELECT", "  COUNT(*) AS _row_count"]

    for col in columns:
        cn = q(col.name, adapter)
        prefix = f'"{col.name}'

        # Universal stats: null count, distinct count
        parts.append(f'  , COUNT({cn}) AS {prefix}__non_null_count"')
        parts.append(f'  , COUNT(DISTINCT {cn}) AS {prefix}__distinct_count"')

        if col.category == "numeric":
            parts.append(f'  , MIN({cn}) AS {prefix}__min"')
            parts.append(f'  , MAX({cn}) AS {prefix}__max"')
            parts.append(f'  , AVG({cn})::DOUBLE AS {prefix}__mean"')
            if adapter == "duckdb":
                parts.append(f'  , MEDIAN({cn}::DOUBLE) AS {prefix}__median"')
            elif adapter == "snowflake":
                parts.append(f'  , MEDIAN({cn}) AS {prefix}__median"')
            else:
                # PostgreSQL: use percentile_cont
                parts.append(
                    f'  , PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {cn}) AS {prefix}__median"'
                )
            parts.append(f'  , STDDEV({cn})::DOUBLE AS {prefix}__stddev"')

        elif col.category == "date":
            parts.append(f'  , MIN({cn})::VARCHAR AS {prefix}__min"')
            parts.append(f'  , MAX({cn})::VARCHAR AS {prefix}__max"')

        elif col.category == "string":
            parts.append(f'  , MIN(LENGTH({cn})) AS {prefix}__min_length"')
            parts.append(f'  , MAX(LENGTH({cn})) AS {prefix}__max_length"')
            parts.append(f'  , AVG(LENGTH({cn}))::DOUBLE AS {prefix}__avg_length"')

    # FROM clause
    table_ref = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
    parts.append(f"FROM {table_ref}")

    # Sampling
    if sample_size and adapter == "duckdb":
        parts.append(f"USING SAMPLE {sample_size} ROWS")
    elif sample_size and adapter == "snowflake":
        parts.append(f"TABLESAMPLE ({sample_size} ROWS)")
    elif sample_size and adapter in ("postgres", "postgresql"):
        # PostgreSQL TABLESAMPLE needs a percentage, use LIMIT instead
        parts.append(f"LIMIT {sample_size}")

    return "\n".join(parts) + ";"


def build_histogram_query(
    schema: str,
    table_name: str,
    column_name: str,
    adapter: str = "duckdb",
    num_bins: int = 10,
) -> str:
    """Build a query to compute a 10-bin histogram for a numeric column.

    Uses WIDTH_BUCKET to distribute values into equal-width bins.
    """
    q = _quote
    cn = q(column_name, adapter)
    table_ref = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'

    if adapter == "duckdb":
        return (
            f"WITH bounds AS (\n"
            f"  SELECT MIN({cn})::DOUBLE AS mn, MAX({cn})::DOUBLE AS mx\n"
            f"  FROM {table_ref} WHERE {cn} IS NOT NULL\n"
            f"), binned AS (\n"
            f"  SELECT WIDTH_BUCKET("
            f"{cn}::DOUBLE, bounds.mn, bounds.mx + 1e-9, "
            f"{num_bins}) AS bucket\n"
            f"  FROM {table_ref}, bounds\n"
            f"  WHERE {cn} IS NOT NULL\n"
            f")\n"
            f"SELECT bucket, COUNT(*) AS freq\n"
            f"FROM binned GROUP BY bucket ORDER BY bucket;"
        )
    # PostgreSQL / Snowflake fallback
    return (
        f"WITH bounds AS (\n"
        f"  SELECT MIN({cn})::DOUBLE PRECISION AS mn, MAX({cn})::DOUBLE PRECISION AS mx\n"
        f"  FROM {table_ref} WHERE {cn} IS NOT NULL\n"
        f"), binned AS (\n"
        f"  SELECT WIDTH_BUCKET("
        f"{cn}::DOUBLE PRECISION, bounds.mn, bounds.mx + 1e-9, "
        f"{num_bins}) AS bucket\n"
        f"  FROM {table_ref}, bounds\n"
        f"  WHERE {cn} IS NOT NULL\n"
        f")\n"
        f"SELECT bucket, COUNT(*) AS freq\n"
        f"FROM binned GROUP BY bucket ORDER BY bucket;"
    )


def build_top_values_query(
    schema: str,
    table_name: str,
    column_name: str,
    adapter: str = "duckdb",
    limit: int = 10,
) -> str:
    """Build a query to get top frequent values for a column."""
    q = _quote
    cn = q(column_name, adapter)
    table_ref = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
    return (
        f"SELECT {cn} AS value, COUNT(*) AS frequency\n"
        f"FROM {table_ref}\n"
        f"WHERE {cn} IS NOT NULL\n"
        f"GROUP BY {cn}\n"
        f"ORDER BY frequency DESC\n"
        f"LIMIT {limit};"
    )
