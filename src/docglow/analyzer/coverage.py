"""Documentation and test coverage analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CoverageResult:
    total: int
    covered: int

    @property
    def rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.covered / self.total


@dataclass(frozen=True)
class CoverageReport:
    models_documented: CoverageResult
    columns_documented: CoverageResult
    models_tested: CoverageResult
    columns_tested: CoverageResult
    coverage_by_folder: dict[str, CoverageResult]
    undocumented_models: list[dict[str, Any]]
    untested_models: list[dict[str, Any]]


def compute_coverage(
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
) -> CoverageReport:
    """Compute documentation and test coverage across all resources."""
    all_models = {**models, **seeds, **snapshots}

    # Documentation coverage
    models_with_desc = 0
    total_columns = 0
    columns_with_desc = 0
    models_with_tests = 0
    columns_with_tests = 0

    # Per-folder coverage
    folder_totals: dict[str, int] = {}
    folder_documented: dict[str, int] = {}

    # Undocumented/untested tracking
    undocumented: list[dict[str, Any]] = []
    untested: list[dict[str, Any]] = []

    for uid, model in all_models.items():
        folder = model.get("folder", "")
        has_desc = bool(model.get("description", "").strip())
        has_tests = len(model.get("test_results", [])) > 0
        downstream_count = len(model.get("referenced_by", []))

        folder_totals[folder] = folder_totals.get(folder, 0) + 1

        if has_desc:
            models_with_desc += 1
            folder_documented[folder] = folder_documented.get(folder, 0) + 1
        else:
            undocumented.append({
                "unique_id": uid,
                "name": model.get("name", ""),
                "folder": folder,
                "downstream_count": downstream_count,
            })

        if has_tests:
            models_with_tests += 1
        else:
            untested.append({
                "unique_id": uid,
                "name": model.get("name", ""),
                "folder": folder,
                "downstream_count": downstream_count,
            })

        for col in model.get("columns", []):
            total_columns += 1
            if col.get("description", "").strip():
                columns_with_desc += 1
            if len(col.get("tests", [])) > 0:
                columns_with_tests += 1

    # Also count source columns
    for source in sources.values():
        for col in source.get("columns", []):
            total_columns += 1
            if col.get("description", "").strip():
                columns_with_desc += 1

    # Sort undocumented/untested by downstream impact (most depended-on first)
    undocumented.sort(key=lambda x: x["downstream_count"], reverse=True)
    untested.sort(key=lambda x: x["downstream_count"], reverse=True)

    # Build per-folder coverage
    coverage_by_folder: dict[str, CoverageResult] = {}
    for folder in folder_totals:
        coverage_by_folder[folder] = CoverageResult(
            total=folder_totals[folder],
            covered=folder_documented.get(folder, 0),
        )

    total_models = len(all_models)

    return CoverageReport(
        models_documented=CoverageResult(total=total_models, covered=models_with_desc),
        columns_documented=CoverageResult(total=total_columns, covered=columns_with_desc),
        models_tested=CoverageResult(total=total_models, covered=models_with_tests),
        columns_tested=CoverageResult(total=total_columns, covered=columns_with_tests),
        coverage_by_folder=coverage_by_folder,
        undocumented_models=undocumented,
        untested_models=untested,
    )
