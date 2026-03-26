"""Role inference, semantic type detection, and confidence scoring."""

from __future__ import annotations

import re


def infer_semantic_type(column_name: str, data_type: str) -> str | None:
    """Infer a semantic type from column name patterns and data type.

    Returns one of: identifier, timestamp, boolean, amount, count,
    categorical, name, email, url, percentage — or None.
    """
    lower = column_name.lower()

    # Name-based patterns (order matters — first match wins)
    patterns: list[tuple[str, str]] = [
        (r".*_id$|.*_key$|^id$", "identifier"),
        (r".*_at$|.*_date$|.*_time$|.*_timestamp$|^created_.*|^updated_.*", "timestamp"),
        (r"^is_.*|^has_.*|^was_.*", "boolean"),
        (r".*_amount$|.*_total$|.*_price$|.*_cost$|.*_revenue$|.*_fee$", "amount"),
        (r".*_count$|.*_num$|.*_qty$|.*_quantity$", "count"),
        (r".*_pct$|.*_percent$|.*_rate$|.*_ratio$", "percentage"),
        (r".*_status$|.*_state$|.*_type$|.*_category$|^status$|^type$", "categorical"),
        (r".*_name$|.*_title$|.*_label$|^name$", "name"),
        (r".*_email$|^email$", "email"),
        (r".*_url$|.*_uri$|.*_link$", "url"),
    ]

    for pattern, semantic in patterns:
        if re.match(pattern, lower):
            return semantic

    # Data type fallback
    dt = data_type.upper()
    if dt in ("BOOLEAN", "BOOL"):
        return "boolean"
    if any(t in dt for t in ("TIMESTAMP", "DATE", "DATETIME")):
        return "timestamp"

    return None


def infer_role(
    column_name: str,
    data_type: str,
    tests: list[dict[str, object]],
    sql_usage: set[str],
    semantic_type: str | None,
) -> str | None:
    """Infer the column's role based on tests, SQL usage, and semantic type.

    Returns one of: primary_key, foreign_key, timestamp, metric,
    categorical, dimension — or None.
    """
    test_types = {t.get("test_type", "") for t in tests}

    # Primary key: unique + not_null tests
    if "unique" in test_types and "not_null" in test_types:
        return "primary_key"

    # Foreign key: relationships test, or identifier used as join key without unique
    if "relationships" in test_types:
        return "foreign_key"
    if semantic_type == "identifier" and "join_key" in sql_usage and "unique" not in test_types:
        return "foreign_key"

    # Timestamp
    if semantic_type == "timestamp":
        return "timestamp"

    # Metric: numeric semantic types or aggregated in SQL
    if semantic_type in ("amount", "count", "percentage") or "aggregated" in sql_usage:
        return "metric"

    # Categorical: accepted_values test or categorical semantic type
    if "accepted_values" in test_types or semantic_type == "categorical":
        return "categorical"

    # Dimension: name-like types or used in GROUP BY
    if semantic_type in ("name", "email", "url") or "group_by" in sql_usage:
        return "dimension"

    return None


def compute_confidence(
    role: str | None,
    tests: list[dict[str, object]],
    sql_usage: set[str],
    semantic_type: str | None,
) -> float:
    """Compute a confidence score (0–1) for the inferred role."""
    if role is None:
        return 0.0

    score = 0.5
    test_types = {t.get("test_type", "") for t in tests}

    # Test evidence bonus
    role_test_map: dict[str, set[str]] = {
        "primary_key": {"unique", "not_null"},
        "foreign_key": {"relationships"},
        "categorical": {"accepted_values"},
    }
    if role in role_test_map and role_test_map[role] & test_types:
        score += 0.2

    # SQL usage bonus
    role_usage_map: dict[str, set[str]] = {
        "primary_key": {"join_key"},
        "foreign_key": {"join_key", "filtered"},
        "dimension": {"group_by"},
        "metric": {"aggregated"},
        "categorical": {"filtered"},
    }
    if role in role_usage_map and role_usage_map[role] & sql_usage:
        score += 0.2

    # Naming pattern bonus
    role_semantic_map: dict[str, set[str]] = {
        "primary_key": {"identifier"},
        "foreign_key": {"identifier"},
        "timestamp": {"timestamp"},
        "metric": {"amount", "count", "percentage"},
        "categorical": {"categorical"},
        "dimension": {"name", "email", "url"},
    }
    if role in role_semantic_map and semantic_type in role_semantic_map[role]:
        score += 0.1

    return min(score, 1.0)
