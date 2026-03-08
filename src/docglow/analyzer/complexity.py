"""Model SQL complexity analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from docglow.config import ComplexityThresholds


@dataclass(frozen=True)
class ModelComplexity:
    unique_id: str
    name: str
    folder: str
    sql_lines: int
    join_count: int
    cte_count: int
    subquery_count: int
    downstream_count: int
    is_high_complexity: bool


@dataclass(frozen=True)
class ComplexityReport:
    models: list[ModelComplexity]
    high_complexity_count: int
    total_count: int

    @property
    def compliance_rate(self) -> float:
        if self.total_count == 0:
            return 1.0
        return 1.0 - (self.high_complexity_count / self.total_count)


_JOIN_PATTERN = re.compile(r"\bjoin\b", re.IGNORECASE)
_CTE_PATTERN = re.compile(r"\bwith\b\s+\w+\s+as\s*\(|\),\s*\w+\s+as\s*\(", re.IGNORECASE)
_SUBQUERY_PATTERN = re.compile(r"\(\s*select\b", re.IGNORECASE)


def _count_joins(sql: str) -> int:
    return len(_JOIN_PATTERN.findall(sql))


def _count_ctes(sql: str) -> int:
    # Count WITH ... AS ( and , name AS ( patterns
    with_count = len(re.findall(r"\bwith\b", sql, re.IGNORECASE))
    as_paren = len(re.findall(r"\bas\s*\(", sql, re.IGNORECASE))
    # CTEs = number of AS ( patterns, but only in CTE context
    # Simple heuristic: count AS ( patterns
    return max(as_paren - with_count, 0) + with_count if as_paren > 0 else 0


def _count_subqueries(sql: str) -> int:
    return len(_SUBQUERY_PATTERN.findall(sql))


def analyze_complexity(
    models: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    thresholds: ComplexityThresholds | None = None,
) -> ComplexityReport:
    """Analyze SQL complexity for all models."""
    if thresholds is None:
        thresholds = ComplexityThresholds()

    all_models = {**models, **seeds, **snapshots}
    results: list[ModelComplexity] = []
    high_count = 0

    for uid, model in all_models.items():
        sql = model.get("compiled_sql", "") or model.get("raw_sql", "")
        sql_lines = len(sql.strip().splitlines()) if sql.strip() else 0
        join_count = _count_joins(sql)
        cte_count = _count_ctes(sql)
        subquery_count = _count_subqueries(sql)
        downstream_count = len(model.get("referenced_by", []))

        is_high = (
            sql_lines > thresholds.high_sql_lines
            or join_count > thresholds.high_join_count
            or cte_count > thresholds.high_cte_count
        )

        if is_high:
            high_count += 1

        results.append(ModelComplexity(
            unique_id=uid,
            name=model.get("name", ""),
            folder=model.get("folder", ""),
            sql_lines=sql_lines,
            join_count=join_count,
            cte_count=cte_count,
            subquery_count=subquery_count,
            downstream_count=downstream_count,
            is_high_complexity=is_high,
        ))

    # Sort by complexity indicators (most complex first)
    results.sort(key=lambda m: (m.sql_lines + m.join_count * 10 + m.cte_count * 5), reverse=True)

    return ComplexityReport(
        models=results,
        high_complexity_count=high_count,
        total_count=len(results),
    )
