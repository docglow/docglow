"""Parse compiled SQL to extract column-level lineage using SQLGlot."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# {database: {schema: {table: {column: type}}}} — nested schema shape used by
# SQLGlot's qualify() to expand qualified star expressions.
NestedSchema = dict[str, dict[str, dict[str, dict[str, str]]]]

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
    "athena": "presto",
    "sqlserver": "tsql",
    "fabric": "tsql",
    "oracle": "oracle",
    "starburst": "trino",
}


@dataclass(frozen=True)
class ColumnDependency:
    """A single column-level dependency."""

    source_table: str  # Table name as parsed from SQL (e.g. "schema.table")
    source_column: str  # Column name in the source table
    transformation: str  # "passthrough" | "rename" | "aggregated" | "derived" | "unknown"


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
    schema: NestedSchema | None = None,
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
    root_statement = None
    for statement in parsed:
        if statement is None:
            continue
        select_stmt = statement.find(exp.Select)
        if select_stmt:
            root_statement = statement
            break

    if select_stmt is None or root_statement is None:
        return {}

    # Expand qualified stars (e.g. renamed.*) into their real columns using
    # the nested schema, before we look at the SELECT clause. On any failure
    # (schema too sparse, unresolvable ref, etc.) fall back to the unqualified
    # tree — the existing star-handling below still applies to it.
    if schema:
        try:
            from sqlglot.optimizer.qualify import qualify

            qualified = qualify(root_statement, schema=schema, infer_schema=True)
            qualified_select = qualified.find(exp.Select)
            if qualified_select is not None:
                select_stmt = qualified_select
        except Exception as e:  # noqa: BLE001
            logger.debug("qualify() failed, falling back to unqualified tree: %s", e)

        # qualify() gives up on expanding *any* star in the SELECT list if
        # even one referenced table can't be resolved from schema (e.g. one
        # side of a join points at a table missing from both schema and
        # known_columns). Manually expand what qualify() left behind so a
        # partially-resolvable join still reports the resolvable side's
        # columns instead of degrading to nothing.
        if any(_is_star_expr(e) for e in select_stmt.expressions):
            select_stmt = _expand_resolvable_qualified_stars(select_stmt, schema)

    # Extract output column names from the SELECT clause
    output_columns = _extract_output_columns(select_stmt)

    # Check for SELECT * EXCLUDE(...) pattern
    excluded_cols = _get_excluded_columns(select_stmt)

    # Detect if outermost SELECT uses * or * EXCLUDE (bare star or a qualified
    # star like `a.*`, which sqlglot represents as Column(this=Star)).
    has_star = any(_is_star_expr(expr) for expr in select_stmt.expressions)

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

    # Star expansion across a join can produce the same output name from
    # multiple sources (e.g. both sides of a join have an `id` column).
    # Keep only the first occurrence so we trace and report it once.
    deduped_columns = list(dict.fromkeys(output_columns))
    if len(deduped_columns) != len(output_columns):
        seen: set[str] = set()
        for name in output_columns:
            if name in seen:
                logger.debug(
                    "Collapsing duplicate star output column '%s' to its first source",
                    name,
                )
            seen.add(name)
    output_columns = deduped_columns

    # If the outermost SELECT uses *, rewrite it to explicit columns
    # so SQLGlot's lineage() can trace through
    trace_sql = compiled_sql
    if has_star and output_columns:
        trace_sql = _rewrite_star_to_columns(compiled_sql, output_columns, dialect)

    # Trace lineage for each output column with a per-column timeout.
    # Reuse a single executor across all columns to avoid the overhead of
    # creating/destroying a ThreadPoolExecutor for every column.
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    result: dict[str, list[ColumnDependency]] = {}
    failures: list[str] = []
    resolved_schema = schema or {}

    with ThreadPoolExecutor(max_workers=1) as executor:
        for col_name in output_columns:
            try:
                deps = _trace_column_in_executor(
                    executor,
                    col_name,
                    trace_sql,
                    resolved_schema,
                    dialect,
                )
                if deps:
                    result[col_name] = deps
            except FuturesTimeout:
                logger.debug("Timeout tracing lineage for column '%s'", col_name)
                failures.append(col_name)
            except Exception as e:  # noqa: BLE001
                logger.debug("Failed to trace lineage for column '%s': %s", col_name, e)
                failures.append(col_name)

    if failures:
        logger.debug(
            "Column lineage: %d/%d columns could not be traced",
            len(failures),
            len(output_columns),
        )

    return result


def _trace_column_in_executor(
    executor: Any,
    col_name: str,
    sql: str,
    schema: NestedSchema,
    dialect: str | None,
    timeout_seconds: int = 2,
) -> list[ColumnDependency]:
    """Trace lineage for a single column using a shared executor for timeout."""
    from concurrent.futures import TimeoutError as FuturesTimeout

    from sqlglot.lineage import lineage

    def _trace() -> list[ColumnDependency]:
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

    future = executor.submit(_trace)
    try:
        result: list[ColumnDependency] = future.result(timeout=timeout_seconds)
        return result
    except FuturesTimeout:
        # Best-effort cancel — the thread may still be running since Python
        # threads can't be forcibly interrupted, but this prevents the result
        # from being collected if it finishes later.
        future.cancel()
        raise


def _rewrite_star_to_columns(
    sql: str,
    columns: list[str],
    dialect: str | None,
) -> str:
    """Rewrite the outermost SELECT * while preserving explicit expressions.

    SQLGlot's lineage() cannot trace columns through SELECT * from a CTE.
    By replacing `SELECT * FROM cte` with `SELECT col1, col2 FROM cte`,
    lineage() can resolve each column through the CTE definitions. Any
    non-star expressions in the SELECT list are retained unchanged.
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

    # Only rewrite if the outermost SELECT contains a star (bare or qualified)
    has_star = any(_is_star_expr(expr) for expr in outermost.expressions)
    if not has_star:
        return sql

    # Do not add a star-expanded column when an explicit expression already
    # produces that name (for example, ``SELECT expr AS id, *``).
    explicit_names = {
        expression.alias_or_name.lower()
        for expression in outermost.expressions
        if not isinstance(expression, exp.Star) and expression.alias_or_name
    }
    star_exprs = [
        exp.Column(this=exp.to_identifier(column))
        for column in columns
        if column.lower() not in explicit_names
    ]

    # Preserve explicit expressions and replace only the Star, at its original
    # position in the projection list.
    new_exprs = []
    for expression in outermost.expressions:
        if _is_star_expr(expression):
            new_exprs.extend(star_exprs)
        else:
            new_exprs.append(expression)

    outermost.set("expressions", new_exprs)

    result: str = tree.sql(dialect=dialect)
    return result


def _expand_resolvable_qualified_stars(select: Any, schema: NestedSchema) -> Any:
    """Expand qualified stars (``a.*``) whose table is present in ``schema``,
    leaving stars for unresolvable tables untouched.

    ``qualify()`` bails on expanding every star in the SELECT list if even one
    referenced table can't be found in schema — this resolves what it can
    directly against the flat schema mapping so a half-resolvable join still
    reports the resolvable side's columns rather than nothing at all.
    """
    from sqlglot import exp

    alias_to_table: dict[str, Any] = {}
    for table in select.find_all(exp.Table):
        alias = table.alias_or_name
        if alias:
            alias_to_table[alias.lower()] = table

    new_expressions: list[Any] = []
    changed = False
    for expression in select.expressions:
        if not (isinstance(expression, exp.Column) and _is_star_expr(expression)):
            new_expressions.append(expression)
            continue

        table_id = expression.args.get("table")
        alias = table_id.this if table_id is not None else None
        table = alias_to_table.get(str(alias).lower()) if alias else None
        columns = _lookup_schema_columns(schema, table) if table is not None else None

        if not columns:
            new_expressions.append(expression)
            continue

        excluded = _star_expr_excluded_columns(expression)
        column_names = [name for name in columns if name.lower() not in excluded]

        changed = True
        new_expressions.extend(exp.column(column_name, table=alias) for column_name in column_names)

    if changed:
        select.set("expressions", new_expressions)
    return select


def _lookup_schema_columns(schema: NestedSchema, table: Any) -> dict[str, str] | None:
    """Look up a table's column mapping in the nested schema dict.

    Tries progressively shorter ``(catalog, db, name)`` suffixes against the
    schema root to match schemas of varying nesting depth (table-only,
    db.table, or catalog.db.table).
    """
    parts = [p for p in (table.catalog, table.db, table.name) if p]
    for start in range(len(parts) - 1, -1, -1):
        node: Any = schema
        for part in parts[start:]:
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if isinstance(node, dict) and node and all(not isinstance(v, dict) for v in node.values()):
            return node
    return None


def _is_star_expr(expression: Any) -> bool:
    """True for a bare star (``*``) or a qualified star (``a.*``).

    SQLGlot represents a bare star as ``exp.Star`` but a qualified star as
    ``exp.Column(this=exp.Star())`` — callers that only check ``isinstance(x,
    exp.Star)`` silently miss the qualified form (e.g. when ``qualify()``
    can't resolve the referenced table and leaves it in place).
    """
    from sqlglot import exp

    if isinstance(expression, exp.Star):
        return True
    return isinstance(expression, exp.Column) and isinstance(expression.this, exp.Star)


def _extract_output_columns(select: Any) -> list[str]:
    """Extract output column names from a SELECT expression."""
    from sqlglot import exp

    columns: list[str] = []
    for expression in select.expressions:
        if isinstance(expression, exp.Alias):
            columns.append(expression.alias)
        elif isinstance(expression, exp.Column) and isinstance(expression.this, exp.Star):
            # Qualified star (e.g. renamed.* or a.*) — never emit a literal "*"
            # as an output column name.
            continue
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


def _star_expr_excluded_columns(expression: Any) -> set[str]:
    """Extract EXCLUDE/EXCEPT column names from a star expression.

    Handles both the bare-star form (``exp.Star``) and the qualified-star form
    (``exp.Column(this=exp.Star())``, e.g. ``a.* EXCLUDE (x)``) — the EXCLUDE
    clause hangs off the inner ``Star`` node either way.
    """
    from sqlglot import exp

    star = expression.this if isinstance(expression, exp.Column) else expression
    if not isinstance(star, exp.Star):
        return set()

    excluded: set[str] = set()
    for child in star.walk():
        if isinstance(child, exp.Column):
            excluded.add(child.name.lower())
    return excluded


def _get_excluded_columns(select: Any) -> set[str]:
    """Extract column names from EXCLUDE/EXCEPT clause in SELECT * EXCLUDE(...)."""
    excluded: set[str] = set()
    for expression in select.expressions:
        excluded |= _star_expr_excluded_columns(expression)
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
        "passthrough" — column passes through unchanged (SELECT a FROM ...)
        "aggregated" — column is inside an aggregate function (SUM, COUNT, etc.)
        "derived" — column is transformed in some other way (CASE, CONCAT, etc.)
        "unknown" — expression is None (could not be parsed)
    """
    from sqlglot import exp

    if expression is None:
        return "unknown"

    # Unwrap Alias to get the actual expression
    inner = expression
    if isinstance(inner, exp.Alias):
        inner = inner.this

    # Simple column reference — passthrough (rename detection deferred to Phase 2)
    if isinstance(inner, exp.Column):
        return "passthrough"

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
) -> NestedSchema:
    """Build a schema mapping for SQLGlot from docglow model/source data.

    Returns a nested dict of {database: {schema: {table: {column: type}}}}
    that SQLGlot's MappingSchema can use to expand SELECT * expressions,
    including qualified stars (e.g. `alias.*`).
    """
    schema: NestedSchema = {}

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
        if not database or not schema_name:
            continue

        schema.setdefault(database, {}).setdefault(schema_name, {})[name] = col_map

    return schema
