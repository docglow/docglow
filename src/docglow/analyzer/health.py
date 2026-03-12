"""Project health scoring engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from docglow.analyzer.complexity import ComplexityReport, analyze_complexity
from docglow.analyzer.coverage import CoverageReport, compute_coverage
from docglow.analyzer.naming import NamingReport, check_naming
from docglow.config import HealthConfig


@dataclass(frozen=True)
class HealthScore:
    overall: float  # 0-100
    documentation: float  # 0-100
    testing: float  # 0-100
    freshness: float  # 0-100
    complexity: float  # 0-100
    naming: float  # 0-100
    orphans: float  # 0-100
    grade: str  # A, B, C, D, F


@dataclass(frozen=True)
class HealthReport:
    score: HealthScore
    coverage: CoverageReport
    complexity: ComplexityReport
    naming: NamingReport
    orphan_models: list[dict[str, Any]]


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _compute_freshness_score(
    sources: dict[str, dict[str, Any]],
) -> float:
    """Compute freshness score from source freshness data."""
    monitored = [s for s in sources.values() if s.get("freshness_status") is not None]
    if not monitored:
        return 100.0  # No monitored sources = not applicable, full score

    passing = sum(
        1
        for s in monitored
        if s.get("freshness_status") in ("pass", "runtime error")
        # "runtime error" means freshness was checked but source had issues,
        # still counts as "monitored"
    )
    warn = sum(1 for s in monitored if s.get("freshness_status") == "warn")
    # Warn counts as partial pass
    return ((passing + warn * 0.5) / len(monitored)) * 100.0


def _find_orphans(
    models: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find models with no downstream consumers."""
    all_models = {**models, **seeds, **snapshots}
    orphans: list[dict[str, Any]] = []

    for uid, model in all_models.items():
        referenced_by = model.get("referenced_by", [])
        if len(referenced_by) == 0:
            orphans.append(
                {
                    "unique_id": uid,
                    "name": model.get("name", ""),
                    "folder": model.get("folder", ""),
                }
            )

    return orphans


def compute_health(
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    config: HealthConfig | None = None,
) -> HealthReport:
    """Compute the overall project health report."""
    if config is None:
        config = HealthConfig()

    weights = config.weights

    # Coverage analysis
    coverage = compute_coverage(models, sources, seeds, snapshots)

    # Documentation score: avg of model + column coverage
    doc_score = ((coverage.models_documented.rate + coverage.columns_documented.rate) / 2) * 100.0

    # Test score: avg of model + column test coverage
    test_score = ((coverage.models_tested.rate + coverage.columns_tested.rate) / 2) * 100.0

    # Freshness score
    freshness_score = _compute_freshness_score(sources)

    # Complexity analysis
    complexity = analyze_complexity(models, seeds, snapshots, config.complexity)
    complexity_score = complexity.compliance_rate * 100.0

    # Naming analysis
    naming = check_naming(models, config.naming_rules)
    naming_score = naming.compliance_rate * 100.0

    # Orphan analysis
    orphans = _find_orphans(models, seeds, snapshots)
    total_models = len(models) + len(seeds) + len(snapshots)
    orphan_rate = len(orphans) / total_models if total_models > 0 else 0.0
    orphan_score = (1.0 - orphan_rate) * 100.0

    # Weighted overall score
    overall = (
        doc_score * weights.documentation
        + test_score * weights.testing
        + freshness_score * weights.freshness
        + complexity_score * weights.complexity
        + naming_score * weights.naming
        + orphan_score * weights.orphans
    )

    score = HealthScore(
        overall=round(overall, 1),
        documentation=round(doc_score, 1),
        testing=round(test_score, 1),
        freshness=round(freshness_score, 1),
        complexity=round(complexity_score, 1),
        naming=round(naming_score, 1),
        orphans=round(orphan_score, 1),
        grade=_grade(overall),
    )

    return HealthReport(
        score=score,
        coverage=coverage,
        complexity=complexity,
        naming=naming,
        orphan_models=orphans,
    )


def health_to_dict(report: HealthReport) -> dict[str, Any]:
    """Convert a HealthReport to a JSON-serializable dict."""
    return {
        "score": {
            "overall": report.score.overall,
            "documentation": report.score.documentation,
            "testing": report.score.testing,
            "freshness": report.score.freshness,
            "complexity": report.score.complexity,
            "naming": report.score.naming,
            "orphans": report.score.orphans,
            "grade": report.score.grade,
        },
        "coverage": {
            "models_documented": {
                "total": report.coverage.models_documented.total,
                "covered": report.coverage.models_documented.covered,
                "rate": round(report.coverage.models_documented.rate, 4),
            },
            "columns_documented": {
                "total": report.coverage.columns_documented.total,
                "covered": report.coverage.columns_documented.covered,
                "rate": round(report.coverage.columns_documented.rate, 4),
            },
            "models_tested": {
                "total": report.coverage.models_tested.total,
                "covered": report.coverage.models_tested.covered,
                "rate": round(report.coverage.models_tested.rate, 4),
            },
            "columns_tested": {
                "total": report.coverage.columns_tested.total,
                "covered": report.coverage.columns_tested.covered,
                "rate": round(report.coverage.columns_tested.rate, 4),
            },
            "by_folder": {
                folder: {
                    "total": result.total,
                    "covered": result.covered,
                    "rate": round(result.rate, 4),
                }
                for folder, result in report.coverage.coverage_by_folder.items()
            },
            "undocumented_models": report.coverage.undocumented_models,
            "untested_models": report.coverage.untested_models,
        },
        "complexity": {
            "high_count": report.complexity.high_complexity_count,
            "total": report.complexity.total_count,
            "compliance_rate": round(report.complexity.compliance_rate, 4),
            "models": [
                {
                    "unique_id": m.unique_id,
                    "name": m.name,
                    "folder": m.folder,
                    "sql_lines": m.sql_lines,
                    "join_count": m.join_count,
                    "cte_count": m.cte_count,
                    "subquery_count": m.subquery_count,
                    "downstream_count": m.downstream_count,
                    "is_high_complexity": m.is_high_complexity,
                }
                for m in report.complexity.models
                if m.is_high_complexity
            ],
        },
        "naming": {
            "total_checked": report.naming.total_checked,
            "compliant_count": report.naming.compliant_count,
            "compliance_rate": round(report.naming.compliance_rate, 4),
            "violations": [
                {
                    "unique_id": v.unique_id,
                    "name": v.name,
                    "folder": v.folder,
                    "expected_pattern": v.expected_pattern,
                    "layer": v.layer,
                }
                for v in report.naming.violations
            ],
        },
        "orphans": report.orphan_models,
    }
