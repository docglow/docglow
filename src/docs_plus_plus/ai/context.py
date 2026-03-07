"""Build compact project context for AI chat."""

from __future__ import annotations

from typing import Any


def build_ai_context(
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    health: dict[str, Any],
) -> dict[str, Any]:
    """Build a compact project context payload for the AI chat system prompt.

    This context is included in the generated JSON so the frontend can send it
    to the Anthropic API as part of the system prompt.
    """
    total_models = len(models) + len(seeds)

    compact_models = _build_compact_models(models, total_models)
    compact_seeds = _build_compact_models(seeds, total_models)
    compact_sources = _build_compact_sources(sources, total_models)

    return {
        "project_name": metadata.get("project_name", ""),
        "dbt_version": metadata.get("dbt_version", ""),
        "total_models": len(models),
        "total_sources": len(sources),
        "total_seeds": len(seeds),
        "models": compact_models,
        "seeds": compact_seeds,
        "sources": compact_sources,
        "health_summary": _build_health_summary(health),
    }


def _build_compact_models(
    models: dict[str, dict[str, Any]],
    total_count: int,
) -> list[dict[str, Any]]:
    """Build compact model entries for AI context.

    Context size tiers:
      - <=200 models: include columns + description (full detail)
      - 201-500 models: include description, omit columns
      - >500 models: omit both columns and description
    """
    include_columns = total_count <= 200
    include_description = total_count <= 500

    entries: list[dict[str, Any]] = []
    for model in models.values():
        test_results = model.get("test_results", [])
        test_status: dict[str, int] = {}
        for t in test_results:
            status = t.get("status", "not_run")
            test_status[status] = test_status.get(status, 0) + 1

        entry: dict[str, Any] = {
            "name": model.get("name", ""),
            "materialization": model.get("materialization", ""),
            "schema": model.get("schema", ""),
            "tags": model.get("tags", []),
            "depends_on": [d.split(".")[-1] for d in model.get("depends_on", [])],
            "referenced_by": [r.split(".")[-1] for r in model.get("referenced_by", [])],
        }

        if include_description:
            entry["description"] = model.get("description", "")

        if test_status:
            entry["test_status"] = test_status

        row_count = (model.get("catalog_stats") or {}).get("row_count")
        if row_count is not None:
            entry["row_count"] = row_count

        if include_columns:
            entry["columns"] = [c.get("name", "") for c in model.get("columns", [])]

        entries.append(entry)

    return entries


def _build_compact_sources(
    sources: dict[str, dict[str, Any]],
    total_model_count: int,
) -> list[dict[str, Any]]:
    """Build compact source entries for AI context."""
    include_columns = total_model_count <= 500

    entries: list[dict[str, Any]] = []
    for source in sources.values():
        entry: dict[str, Any] = {
            "name": f"{source.get('source_name', '')}.{source.get('name', '')}",
            "description": source.get("description", ""),
            "schema": source.get("schema", ""),
        }

        if include_columns:
            entry["columns"] = [c.get("name", "") for c in source.get("columns", [])]

        if source.get("freshness_status"):
            entry["freshness_status"] = source["freshness_status"]

        entries.append(entry)

    return entries


def _build_health_summary(health: dict[str, Any]) -> dict[str, Any]:
    """Build a compact health summary for AI context."""
    score = health.get("score", {})
    coverage = health.get("coverage", {})

    return {
        "overall_score": score.get("overall", 0),
        "grade": score.get("grade", ""),
        "documentation_coverage": coverage.get("models_documented", {}).get("rate", 0),
        "test_coverage": coverage.get("models_tested", {}).get("rate", 0),
        "naming_compliance": health.get("naming", {}).get("compliance_rate", 0),
        "high_complexity_count": health.get("complexity", {}).get("high_count", 0),
        "orphan_count": len(health.get("orphans", [])),
    }
