"""Parse compiled SQL to extract column-level lineage using SQLGlot."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Adapter type -> SQLGlot dialect mapping
_DIALECT_MAP: dict[str, str] = {
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "postgres": "postgres",
    "postgresql": "postgres",
    "redshift": "redshift",
    "duckdb": "duckdb",
    "databricks": "databricks",
    "spark": "spark",
    "trino": "trino",
    "clickhouse": "clickhouse",
}


@dataclass(frozen=True)
class ColumnDependency:
    """A single column-level dependency."""

    source_table: str  # Table name as parsed from SQL (e.g. "schema.table")
    source_column: str  # Column name in the source table
    transformation: str  # "direct" | "derived" | "aggregated"


def detect_dialect(adapter_type: str | None) -> str | None:
    """Map a dbt adapter type to a SQLGlot dialect string.

    Returns None if the adapter type is unknown, which lets SQLGlot
    attempt auto-detection.
    """
    if adapter_type is None:
        return None
    return _DIALECT_MAP.get(adapter_type.lower())


def parse_column_lineage(
    compiled_sql: str,
    schema: dict[str, dict[str, str]] | None = None,
    dialect: str | None = None,
    known_columns: list[str] | None = None,
) -> dict[str, list[ColumnDependency]]:
    """Parse compiled SQL and extract column-level dependencies.

    Args:
        compiled_sql: The compiled SQL string (Jinja already resolved).
        schema: Optional schema mapping of {table_name: {col_name: col_type}}.
            Required for resolving SELECT * expressions.
        dialect: SQL dialect for parsing (e.g. "snowflake", "bigquery").
        known_columns: Optional list of known output column names (e.g. from
            catalog). Used as fallback when the outermost SELECT uses *.

    Returns:
        Dict mapping output column name -> list of upstream ColumnDependency.
        Returns empty dict if SQL cannot be parsed.
    """
    if not compiled_sql or not compiled_sql.strip():
        return {}

    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        logger.warning(
            "sqlglot is not installed. Install with: pip install docglow[column-lineage]"
        )
        return {}

    # Parse the SQL to find output column names
    try:
        parsed = sqlglot.parse(compiled_sql, dialect=dialect)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to parse SQL for column lineage")
        return {}

    if not parsed:
        return {}

    # Get the outermost SELECT statement
    select_stmt = None
    for statement in parsed:
        if statement is None:
            continue
        select_stmt = statement.find(exp.Select)
        if select_stmt:
            break

    if select_stmt is None:
        return {}

    # Extract output column names from the SELECT clause
    output_columns = _extract_output_columns(select_stmt)

    # Check for SELECT * EXCLUDE(...) pattern
    excluded_cols = _get_excluded_columns(select_stmt)

    # Detect if outermost SELECT uses * or * EXCLUDE
    has_star = any(isinstance(expr, exp.Star) for expr in select_stmt.expressions)

    # If SELECT * (with or without EXCLUDE) and we have known columns, use those
    if has_star and known_columns:
        # Start with known columns, remove excluded ones
        star_columns = [c for c in known_columns if c.lower() not in excluded_cols]
        # Remove columns that are already explicitly listed (e.g. aliased CASE exprs)
        explicit_names = {c.lower() for c in output_columns}
        star_columns = [c for c in star_columns if c.lower() not in explicit_names]
        # Prepend star columns before explicit columns
        output_columns = star_columns + output_columns
    elif has_star and not known_columns:
        # No catalog/manifest columns — try to resolve from the CTE definition
        cte_columns = _resolve_star_from_cte(parsed[0], select_stmt, excluded_cols, dialect)
        if cte_columns:
            explicit_names = {c.lower() for c in output_columns}
            cte_columns = [c for c in cte_columns if c.lower() not in explicit_names]
            output_columns = cte_columns + output_columns
            logger.debug(
                "Resolved %d columns from CTE for SELECT * (no catalog data)",
                len(cte_columns),
            )
    elif not output_columns and known_columns:
        output_columns = list(known_columns)

    if not output_columns:
        return {}

    # If the outermost SELECT uses *, rewrite it to explicit columns
    # so SQLGlot's lineage() can trace through
    trace_sql = compiled_sql
    if has_star and output_columns:
        trace_sql = _rewrite_star_to_columns(compiled_sql, output_columns, dialect)

    # Trace lineage for each output column with a per-column timeout
    result: dict[str, list[ColumnDependency]] = {}
    failures: list[str] = []
    for col_name in output_columns:
        try:
            deps = _trace_column_with_timeout(col_name, trace_sql, schema or {}, dialect)
            if deps:
                result[col_name] = deps
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to trace lineage for column '%s': %s", col_name, e)
            failures.append(col_name)
            continue

    if failures:
        logger.debug(
            "Column lineage: %d/%d columns could not be traced",
            len(failures),
            len(output_columns),
        )

    return result


def _trace_column_with_timeout(
    col_name: str,
    sql: str,
    schema: dict[str, dict[str, str]],
    dialect: str | None,
    timeout_seconds: int = 2,
) -> list[ColumnDependency]:
    """Trace lineage for a single column with a thread-safe timeout."""
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    from sqlglot.lineage import lineage

    def _trace() -> Any:
        # Try with schema first (enables SELECT * expansion through CTEs).
        # If it fails, retry without schema (handles cases where schema
        # keys don't match SQL table references or columns are missing).
        try:
            node = lineage(
                column=col_name,
                sql=sql,
                schema=schema or {},
                dialect=dialect,
            )
            deps = _collect_dependencies(node)
            if deps:
                return deps
        except Exception:  # noqa: BLE001
            pass  # Fall through to retry without schema

        # Retry without schema (more lenient — won't resolve SELECT * but
        # won't blow up on unknown columns or variant access syntax)
        try:
            node = lineage(
                column=col_name,
                sql=sql,
                schema={},
                dialect=dialect,
            )
            return _collect_dependencies(node)
        except Exception:  # noqa: BLE001
            return []

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_trace)
        try:
            result: list[ColumnDependency] = future.result(timeout=timeout_seconds)
            return result
        except FuturesTimeout:
            logger.debug("Timeout tracing lineage for column '%s'", col_name)
            future.cancel()
            return []


def _rewrite_star_to_columns(
    sql: str,
    columns: list[str],
    dialect: str | None,
) -> str:
    """Rewrite the outermost SELECT * to list explicit column names.

    SQLGlot's lineage() cannot trace columns through SELECT * from a CTE.
    By replacing `SELECT * FROM cte` with `SELECT col1, col2 FROM cte`,
    lineage() can resolve each column through the CTE definitions.
    """
    import sqlglot
    from sqlglot import exp

    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except Exception:  # noqa: BLE001
        return sql

    if not parsed or parsed[0] is None:
        return sql

    tree = parsed[0]
    outermost = tree.find(exp.Select)
    if outermost is None:
        return sql

    # Only rewrite if the outermost SELECT contains a Star
    has_star = any(isinstance(expr, exp.Star) for expr in outermost.expressions)
    if not has_star:
        return sql

    # Build new column expressions
    new_exprs = [exp.Column(this=exp.to_identifier(c)) for c in columns]
    outermost.set("expressions", new_exprs)

    result: str = tree.sql(dialect=dialect)
    return result


def _extract_output_columns(select: Any) -> list[str]:
    """Extract output column names from a SELECT expression."""
    from sqlglot import exp

    columns: list[str] = []
    for expression in select.expressions:
        if isinstance(expression, exp.Alias):
            columns.append(expression.alias)
        elif isinstance(expression, exp.Column):
            columns.append(expression.name)
        elif isinstance(expression, exp.Star):
            continue
        else:
            alias = expression.alias_or_name
            if alias:
                columns.append(alias)
    return columns


def _resolve_star_from_cte(
    tree: Any,
    outer_select: Any,
    excluded_cols: set[str],
    dialect: str | None,
) -> list[str]:
    """Resolve column names for SELECT * by inspecting the referenced CTE.

    When the outermost SELECT is ``SELECT * FROM some_cte`` and we have no
    catalog/manifest columns, we can look at the CTE definition to find the
    output column names. This handles the common dbt pattern::

        WITH renamed AS (
            SELECT col_a, col_b AS alias_b, ...
            FROM source
        )
        SELECT * FROM renamed
    """
    from sqlglot import exp

    # Find the FROM clause of the outermost SELECT
    from_clause = outer_select.find(exp.From)
    if not from_clause:
        return []

    # Get the table name referenced in FROM
    table = from_clause.find(exp.Table)
    if not table:
        return []

    cte_name = table.name.lower()

    # Find the matching CTE definition
    for cte in tree.find_all(exp.CTE):
        alias = cte.alias
        if not alias or alias.lower() != cte_name:
            continue

        # Found the CTE — extract its output columns
        cte_select = cte.find(exp.Select)
        if not cte_select:
            return []

        # Check if the CTE itself uses SELECT *
        cte_has_star = any(isinstance(e, exp.Star) for e in cte_select.expressions)
        if cte_has_star:
            # CTE also uses SELECT * — we can't resolve further without schema
            return []

        columns = _extract_output_columns(cte_select)

        # Apply EXCLUDE filter
        if excluded_cols:
            columns = [c for c in columns if c.lower() not in excluded_cols]

        return columns

    return []


def _get_excluded_columns(select: Any) -> set[str]:
    """Extract column names from EXCLUDE/EXCEPT clause in SELECT * EXCLUDE(...)."""
    from sqlglot import exp

    excluded: set[str] = set()
    for expression in select.expressions:
        if isinstance(expression, exp.Star):
            # Star may contain EXCLUDE/EXCEPT columns as children
            for child in expression.walk():
                if isinstance(child, exp.Column):
                    excluded.add(child.name.lower())
    return excluded


def _collect_dependencies(root_node: Any) -> list[ColumnDependency]:
    """Walk a SQLGlot lineage node tree and collect leaf dependencies.

    The lineage tree has:
    - root_node: the target column (its .expression shows the full expr)
    - downstream nodes: each has .name like "table.column" and .source

    For nodes with Table sources (true leaves), we extract the table and column.
    When a leaf is a '*' (from SELECT *), we look at the parent node for the
    actual column name.
    """
    from sqlglot import exp

    deps: list[ColumnDependency] = []
    seen: set[tuple[str, str]] = set()

    root_transformation = _classify_transformation(root_node.expression)

    # Collect all nodes with their parent context
    all_nodes: list[tuple[Any, Any | None]] = []
    _walk_with_parent(root_node, None, all_nodes)

    for lineage_node, parent_node in all_nodes:
        if lineage_node is root_node:
            continue

        node_name = lineage_node.name if isinstance(lineage_node.name, str) else ""
        source_column = _extract_column_from_node_name(node_name)

        if isinstance(lineage_node.source, exp.Table):
            source_table = _table_to_string(lineage_node.source)

            # If the leaf is a '*', use the parent's column name instead
            if source_column == "*" and parent_node is not None:
                parent_name = parent_node.name if isinstance(parent_node.name, str) else ""
                parent_col = _extract_column_from_node_name(parent_name)
                if parent_col and parent_col != "*":
                    source_column = parent_col

            if not source_table or not source_column or source_column == "*":
                continue

            key = (source_table.lower(), source_column.lower())
            if key in seen:
                continue
            seen.add(key)

            deps.append(
                ColumnDependency(
                    source_table=source_table,
                    source_column=source_column,
                    transformation=root_transformation,
                )
            )

    return deps


def _walk_with_parent(node: Any, parent: Any | None, result: list[tuple[Any, Any | None]]) -> None:
    """Walk the lineage tree collecting (node, parent) pairs."""
    result.append((node, parent))
    for child in node.downstream:
        _walk_with_parent(child, node, result)


def _table_to_string(table: Any) -> str:
    """Convert a SQLGlot Table expression to a dotted string."""
    parts: list[str] = []
    if table.catalog:
        parts.append(table.catalog)
    if table.db:
        parts.append(table.db)
    parts.append(table.name)
    return ".".join(parts)


def _extract_column_from_node_name(name: str) -> str:
    """Extract the column name from a lineage node name like 'table.column'."""
    if "." in name:
        return name.rsplit(".", 1)[1]
    return name


def _classify_transformation(expression: Any) -> str:
    """Classify the transformation type based on the root node's expression.

    Returns:
        "direct" — column passes through unchanged (SELECT a FROM ...)
        "aggregated" — column is inside an aggregate function (SUM, COUNT, etc.)
        "derived" — column is transformed in some other way (CASE, CONCAT, etc.)
    """
    from sqlglot import exp

    if expression is None:
        return "direct"

    # Unwrap Alias to get the actual expression
    inner = expression
    if isinstance(inner, exp.Alias):
        inner = inner.this

    # Simple column reference
    if isinstance(inner, exp.Column):
        return "direct"

    # Direct aggregate function
    agg_types = (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max, exp.AnyValue)
    if isinstance(inner, agg_types):
        return "aggregated"

    # Check if any descendant is an aggregate (e.g. COALESCE(SUM(x), 0))
    if isinstance(inner, exp.Expression):
        for node in inner.walk():
            if isinstance(node, agg_types):
                return "aggregated"

    return "derived"


def build_schema_mapping(
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Build a schema mapping for SQLGlot from docglow model/source data.

    Returns a dict of {table_reference: {column_name: column_type}} that
    SQLGlot can use to expand SELECT * expressions.
    """
    schema: dict[str, dict[str, str]] = {}

    for data in {**models, **sources}.values():
        name = data.get("name", "")
        schema_name = data.get("schema", "")
        database = data.get("database", "")
        if not name:
            continue
        col_map: dict[str, str] = {}
        for col in data.get("columns", []):
            col_type = col.get("data_type", "")
            col_map[col["name"]] = col_type or "VARCHAR"
        if not col_map:
            continue

        # Index by multiple key formats for flexible matching:
        # bare name, schema.name, database.schema.name
        schema.setdefault(name, col_map)
        if schema_name:
            schema[f"{schema_name}.{name}"] = col_map
            if database:
                schema[f"{database}.{schema_name}.{name}"] = col_map

        # Also index by source_name.table_name for sources
        source_name = data.get("source_name", "")
        if source_name:
            schema.setdefault(f"{source_name}.{name}", col_map)

    return schema
