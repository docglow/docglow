"""Tests for AI context builder."""

import pytest

from docs_plus_plus.ai.context import build_ai_context


def _make_model(name, **overrides):
    base = {
        "unique_id": f"model.pkg.{name}",
        "name": name,
        "description": f"Description of {name}",
        "schema": "public",
        "database": "db",
        "materialization": "table",
        "tags": [],
        "meta": {},
        "path": f"models/{name}.sql",
        "folder": "models",
        "raw_sql": "SELECT 1",
        "compiled_sql": "SELECT 1",
        "columns": [
            {"name": "id", "description": "Primary key", "data_type": "integer",
             "meta": {}, "tags": [], "tests": [], "profile": None},
        ],
        "depends_on": [],
        "referenced_by": [],
        "sources_used": [],
        "test_results": [],
        "last_run": None,
        "catalog_stats": {"row_count": None, "bytes": None, "has_stats": False},
    }
    base.update(overrides)
    return base


def _make_source(name, source_name="raw", **overrides):
    base = {
        "unique_id": f"source.pkg.{source_name}.{name}",
        "name": name,
        "source_name": source_name,
        "description": f"Source {name}",
        "schema": "raw",
        "database": "db",
        "columns": [
            {"name": "id", "description": "", "data_type": "integer",
             "meta": {}, "tags": [], "tests": [], "profile": None},
        ],
        "tags": [],
        "meta": {},
        "loader": "csv",
        "loaded_at_field": None,
        "freshness_status": None,
        "freshness_max_loaded_at": None,
        "freshness_snapshotted_at": None,
    }
    base.update(overrides)
    return base


METADATA = {
    "project_name": "test_project",
    "dbt_version": "1.7.0",
}

HEALTH = {
    "score": {"overall": 75, "grade": "C"},
    "coverage": {
        "models_documented": {"total": 10, "covered": 8, "rate": 0.8},
        "models_tested": {"total": 10, "covered": 6, "rate": 0.6},
    },
    "naming": {"compliance_rate": 0.9},
    "complexity": {"high_count": 2},
    "orphans": [{"unique_id": "model.pkg.orphan", "name": "orphan", "folder": "models"}],
}


class TestBuildAiContext:
    def test_basic_structure(self):
        models = {"m1": _make_model("orders")}
        sources = {"s1": _make_source("raw_orders")}
        seeds = {}

        ctx = build_ai_context(models, sources, seeds, METADATA, HEALTH)

        assert ctx["project_name"] == "test_project"
        assert ctx["dbt_version"] == "1.7.0"
        assert ctx["total_models"] == 1
        assert ctx["total_sources"] == 1
        assert ctx["total_seeds"] == 0
        assert len(ctx["models"]) == 1
        assert len(ctx["sources"]) == 1
        assert len(ctx["seeds"]) == 0

    def test_model_fields(self):
        models = {
            "m1": _make_model(
                "orders",
                tags=["finance"],
                depends_on=["model.pkg.stg_orders"],
                referenced_by=["model.pkg.fct_revenue"],
            )
        }

        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)
        m = ctx["models"][0]

        assert m["name"] == "orders"
        assert m["description"] == "Description of orders"
        assert m["materialization"] == "table"
        assert m["schema"] == "public"
        assert m["tags"] == ["finance"]
        assert m["depends_on"] == ["stg_orders"]
        assert m["referenced_by"] == ["fct_revenue"]

    def test_columns_included_for_small_projects(self):
        models = {"m1": _make_model("orders")}
        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)

        assert "columns" in ctx["models"][0]
        assert ctx["models"][0]["columns"] == ["id"]

    def test_columns_excluded_for_large_projects(self):
        models = {f"m{i}": _make_model(f"model_{i}") for i in range(201)}
        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)

        assert "columns" not in ctx["models"][0]

    def test_test_status_aggregation(self):
        models = {
            "m1": _make_model(
                "orders",
                test_results=[
                    {"test_name": "t1", "status": "pass"},
                    {"test_name": "t2", "status": "pass"},
                    {"test_name": "t3", "status": "fail"},
                ],
            )
        }

        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)
        m = ctx["models"][0]

        assert m["test_status"] == {"pass": 2, "fail": 1}

    def test_test_status_omitted_when_empty(self):
        models = {"m1": _make_model("orders", test_results=[])}
        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)

        assert "test_status" not in ctx["models"][0]

    def test_row_count_included(self):
        models = {
            "m1": _make_model(
                "orders",
                catalog_stats={"row_count": 1000, "bytes": None, "has_stats": True},
            )
        }

        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)
        assert ctx["models"][0]["row_count"] == 1000

    def test_row_count_omitted_when_null(self):
        models = {"m1": _make_model("orders")}
        ctx = build_ai_context(models, {}, {}, METADATA, HEALTH)

        assert "row_count" not in ctx["models"][0]

    def test_source_fields(self):
        sources = {
            "s1": _make_source("raw_orders", source_name="raw_db", freshness_status="pass")
        }

        ctx = build_ai_context({}, sources, {}, METADATA, HEALTH)
        s = ctx["sources"][0]

        assert s["name"] == "raw_db.raw_orders"
        assert s["schema"] == "raw"
        assert s["columns"] == ["id"]
        assert s["freshness_status"] == "pass"

    def test_source_freshness_omitted_when_null(self):
        sources = {"s1": _make_source("raw_orders")}
        ctx = build_ai_context({}, sources, {}, METADATA, HEALTH)

        assert "freshness_status" not in ctx["sources"][0]

    def test_health_summary(self):
        ctx = build_ai_context({}, {}, {}, METADATA, HEALTH)
        h = ctx["health_summary"]

        assert h["overall_score"] == 75
        assert h["grade"] == "C"
        assert h["documentation_coverage"] == 0.8
        assert h["test_coverage"] == 0.6
        assert h["naming_compliance"] == 0.9
        assert h["high_complexity_count"] == 2
        assert h["orphan_count"] == 1

    def test_health_summary_defaults(self):
        ctx = build_ai_context({}, {}, {}, METADATA, {})
        h = ctx["health_summary"]

        assert h["overall_score"] == 0
        assert h["grade"] == ""
        assert h["documentation_coverage"] == 0
        assert h["test_coverage"] == 0

    def test_seeds_separate_from_models(self):
        models = {"m1": _make_model("orders")}
        seeds = {"s1": _make_model("country_codes", materialization="seed")}

        ctx = build_ai_context(models, {}, seeds, METADATA, HEALTH)

        assert ctx["total_models"] == 1
        assert ctx["total_seeds"] == 1
        assert len(ctx["models"]) == 1
        assert len(ctx["seeds"]) == 1
        assert ctx["seeds"][0]["name"] == "country_codes"

    def test_empty_project(self):
        ctx = build_ai_context({}, {}, {}, METADATA, HEALTH)

        assert ctx["total_models"] == 0
        assert ctx["total_sources"] == 0
        assert ctx["total_seeds"] == 0
        assert ctx["models"] == []
        assert ctx["sources"] == []
        assert ctx["seeds"] == []
