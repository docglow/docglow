"""Expand common dbt macros into SQL approximations for column lineage tracing.

Handles well-known macros from dbt-core and dbt-utils to preserve column
references that would otherwise be lost when replaced by NULL placeholders.
Unrecognized macros still fall through to NULL.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# Each handler takes the full regex match and returns a SQL replacement string.
_MacroHandler = Callable[[re.Match[str]], str]

_HANDLERS: list[tuple[re.Pattern[str], _MacroHandler]] = []


def _register(pattern: str, flags: int = 0) -> Callable[[_MacroHandler], _MacroHandler]:
    """Decorator to register a macro pattern handler."""

    def decorator(fn: _MacroHandler) -> _MacroHandler:
        _HANDLERS.append((re.compile(pattern, flags | re.DOTALL), fn))
        return fn

    return decorator


def _extract_string_list(raw: str) -> list[str]:
    """Extract a list of quoted strings from a Jinja argument like "['a', 'b']"."""
    return re.findall(r"""['"]([^'"]+)['"]""", raw)


def _extract_single_arg(raw: str) -> str:
    """Extract a single quoted string argument."""
    match = re.search(r"""['"]([^'"]+)['"]""", raw)
    return match.group(1) if match else raw.strip()


# --- Macro Handlers ---


@_register(
    r"\{\{\s*dbt_utils\.surrogate_key\s*\(\s*(\[.*?\])\s*\)\s*\}\}",
    re.DOTALL,
)
def _surrogate_key(match: re.Match[str]) -> str:
    """dbt_utils.surrogate_key(['col_a', 'col_b']) -> CONCAT(col_a, col_b)"""
    columns = _extract_string_list(match.group(1))
    if not columns:
        return "NULL"
    return f"CONCAT({', '.join(columns)})"


@_register(
    r"\{\{\s*dbt_utils\.star\s*\(\s*(?:ref|source)\s*\(.*?\)\s*"
    r"(?:,\s*except\s*=\s*\[.*?\])?\s*\)\s*\}\}",
    re.DOTALL,
)
def _star(match: re.Match[str]) -> str:
    """dbt_utils.star(ref('model')) -> * (let SQLGlot handle it with known_columns)"""
    return "*"


@_register(
    r"\{\{\s*(?:dbt\.date_trunc|dbt_utils\.date_trunc|datetrunc)\s*\("
    r"\s*['\"](\w+)['\"]\s*,\s*['\"]?(\w+)['\"]?\s*\)\s*\}\}"
)
def _date_trunc(match: re.Match[str]) -> str:
    """dbt.date_trunc('day', 'created_at') -> DATE_TRUNC('day', created_at)"""
    part = match.group(1)
    column = match.group(2)
    return f"DATE_TRUNC('{part}', {column})"


@_register(
    r"\{\{\s*(?:dbt\.safe_cast|dbt_utils\.safe_cast|safe_cast)\s*\("
    r"\s*['\"]?(\w+)['\"]?\s*,\s*(?:api\.Column\.translate_type\s*\(\s*)?['\"](\w+)['\"]"
    r"\s*\)?\s*\)\s*\}\}"
)
def _safe_cast(match: re.Match[str]) -> str:
    """dbt.safe_cast('col', 'integer') -> CAST(col AS integer)"""
    column = match.group(1)
    data_type = match.group(2)
    return f"CAST({column} AS {data_type})"


@_register(
    r"\{\{\s*(?:dbt\.current_timestamp|dbt_utils\.current_timestamp|current_timestamp)\s*\("
    r"\s*\)\s*\}\}"
)
def _current_timestamp(match: re.Match[str]) -> str:
    """dbt.current_timestamp() -> CURRENT_TIMESTAMP"""
    return "CURRENT_TIMESTAMP"


@_register(
    r"\{\{\s*(?:dbt\.datediff|dbt_utils\.datediff|datediff)\s*\("
    r"\s*['\"]?(\w+)['\"]?\s*,\s*['\"]?(\w+)['\"]?\s*,\s*['\"](\w+)['\"]\s*\)\s*\}\}"
)
def _datediff(match: re.Match[str]) -> str:
    """dbt.datediff('start', 'end', 'day') -> DATEDIFF('day', start, end)"""
    start = match.group(1)
    end = match.group(2)
    part = match.group(3)
    return f"DATEDIFF('{part}', {start}, {end})"


@_register(
    r"\{\{\s*(?:dbt\.dateadd|dbt_utils\.dateadd|dateadd)\s*\("
    r"\s*['\"](\w+)['\"]\s*,\s*(-?\d+)\s*,\s*['\"]?(\w+)['\"]?\s*\)\s*\}\}"
)
def _dateadd(match: re.Match[str]) -> str:
    """dbt.dateadd('day', -7, 'created_at') -> DATEADD('day', -7, created_at)"""
    part = match.group(1)
    interval = match.group(2)
    column = match.group(3)
    return f"DATEADD('{part}', {interval}, {column})"


@_register(r"\{\{\s*(?:type_string|dbt\.type_string|dbt_utils\.type_string)\s*\(\s*\)\s*\}\}")
def _type_string(match: re.Match[str]) -> str:
    """{{ type_string() }} -> VARCHAR"""
    return "VARCHAR"


@_register(r"\{\{\s*(?:type_int|dbt\.type_int|dbt_utils\.type_int)\s*\(\s*\)\s*\}\}")
def _type_int(match: re.Match[str]) -> str:
    """{{ type_int() }} -> INTEGER"""
    return "INTEGER"


@_register(
    r"\{\{\s*(?:type_timestamp|dbt\.type_timestamp|dbt_utils\.type_timestamp)\s*\(\s*\)\s*\}\}"
)
def _type_timestamp(match: re.Match[str]) -> str:
    """{{ type_timestamp() }} -> TIMESTAMP"""
    return "TIMESTAMP"


@_register(r"\{\{\s*(?:type_float|dbt\.type_float|dbt_utils\.type_float)\s*\(\s*\)\s*\}\}")
def _type_float(match: re.Match[str]) -> str:
    """{{ type_float() }} -> FLOAT"""
    return "FLOAT"


@_register(r"\{\{\s*(?:type_numeric|dbt\.type_numeric|dbt_utils\.type_numeric)\s*\(\s*\)\s*\}\}")
def _type_numeric(match: re.Match[str]) -> str:
    """{{ type_numeric() }} -> NUMERIC"""
    return "NUMERIC"


@_register(r"\{\{\s*(?:type_boolean|dbt\.type_boolean)\s*\(\s*\)\s*\}\}")
def _type_boolean(match: re.Match[str]) -> str:
    """{{ type_boolean() }} -> BOOLEAN"""
    return "BOOLEAN"


def expand_macros(sql: str) -> str:
    """Expand known dbt macros in Jinja-templated SQL to SQL approximations.

    Applies registered macro handlers in order. Each handler replaces its
    matched pattern with a SQL approximation that preserves column references.
    Unrecognized ``{{ ... }}`` expressions are NOT touched by this function —
    the caller should apply a fallback (e.g. replace with NULL) afterward.
    """
    for pattern, handler in _HANDLERS:
        sql = pattern.sub(handler, sql)
    return sql
