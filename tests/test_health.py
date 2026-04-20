"""Tests for the health analysis engine."""

from typing import Any

from docglow.analyzer.complexity import analyze_complexity
from docglow.analyzer.coverage import compute_coverage
from docglow.analyzer.health import compute_health, health_to_dict
from docglow.analyzer.naming import check_naming
from docglow.config import ComplexityThresholds, NamingRules


def _make_model(
    uid: str = "model.pkg.test_model",
    name: str = "test_model",
    description: str = "",
    folder: str = "models",
    path: str = "models/test_model.sql",
    columns: list[dict[str, Any]] | None = None,
    test_results: list[dict[str, Any]] | None = None,
    referenced_by: list[str] | None = None,
    compiled_sql: str = "SELECT 1",
    raw_sql: str = "SELECT 1",
    materialization: str = "table",
) -> dict[str, Any]:
    return {
        "unique_id": uid,
        "name": name,
        "description": description,
        "folder": folder,
        "path": path,
        "columns": columns or [],
        "test_results": test_results or [],
        "referenced_by": referenced_by or [],
        "compiled_sql": compiled_sql,
        "raw_sql": raw_sql,
        "materialization": materialization,
        "schema": "public",
        "database": "db",
        "tags": [],
        "meta": {},
        "depends_on": [],
        "sources_used": [],
        "last_run": None,
        "catalog_stats": {"row_count": None, "bytes": None, "has_stats": False},
    }


def _make_source(
    uid: str = "source.pkg.db.table1",
    name: str = "table1",
    source_name: str = "db",
    columns: list[dict[str, Any]] | None = None,
    freshness_status: str | None = None,
) -> dict[str, Any]:
    return {
        "unique_id": uid,
        "name": name,
        "source_name": source_name,
        "description": "",
        "schema": "public",
        "database": "db",
        "columns": columns or [],
        "tags": [],
        "meta": {},
        "loader": "",
        "loaded_at_field": None,
        "freshness_status": freshness_status,
        "freshness_max_loaded_at": None,
        "freshness_snapshotted_at": None,
    }


class TestCoverage:
    def test_full_coverage(self) -> None:
        models = {
            "m1": _make_model(
                description="documented",
                columns=[{"name": "id", "description": "pk", "tests": [{"test_name": "t"}]}],
                test_results=[{"status": "pass"}],
            ),
        }
        result = compute_coverage(models, {}, {}, {})
        assert result.models_documented.rate == 1.0
        assert result.models_tested.rate == 1.0
        assert result.columns_documented.rate == 1.0

    def test_zero_coverage(self) -> None:
        models = {
            "m1": _make_model(columns=[{"name": "id", "description": "", "tests": []}]),
        }
        result = compute_coverage(models, {}, {}, {})
        assert result.models_documented.rate == 0.0
        assert result.models_tested.rate == 0.0
        assert result.columns_documented.rate == 0.0

    def test_partial_coverage(self) -> None:
        models = {
            "m1": _make_model(description="yes", test_results=[{"status": "pass"}]),
            "m2": _make_model(uid="model.pkg.m2", name="m2"),
        }
        result = compute_coverage(models, {}, {}, {})
        assert result.models_documented.rate == 0.5
        assert result.models_tested.rate == 0.5

    def test_undocumented_sorted_by_impact(self) -> None:
        models = {
            "m1": _make_model(uid="model.pkg.m1", name="m1", referenced_by=["x"]),
            "m2": _make_model(uid="model.pkg.m2", name="m2", referenced_by=["x", "y", "z"]),
        }
        result = compute_coverage(models, {}, {}, {})
        assert result.undocumented_models[0]["name"] == "m2"

    def test_per_folder_coverage(self) -> None:
        models = {
            "m1": _make_model(uid="m1", name="m1", folder="staging", description="yes"),
            "m2": _make_model(uid="m2", name="m2", folder="staging"),
            "m3": _make_model(uid="m3", name="m3", folder="marts", description="yes"),
        }
        result = compute_coverage(models, {}, {}, {})
        assert result.coverage_by_folder["staging"].rate == 0.5
        assert result.coverage_by_folder["marts"].rate == 1.0

    def test_empty_project(self) -> None:
        result = compute_coverage({}, {}, {}, {})
        assert result.models_documented.rate == 1.0
        assert result.columns_documented.rate == 1.0


class TestComplexity:
    def test_simple_sql(self) -> None:
        models = {"m1": _make_model(compiled_sql="SELECT id FROM t")}
        result = analyze_complexity(models, {}, {})
        assert result.high_complexity_count == 0
        assert result.models[0].join_count == 0

    def test_complex_sql(self) -> None:
        joins = " JOIN ".join("abcdefghij")
        sql = "\n".join([f"-- line {i}" for i in range(250)]) + f"\nSELECT * FROM {joins}"
        models = {"m1": _make_model(compiled_sql=sql)}
        result = analyze_complexity(models, {}, {}, ComplexityThresholds(high_sql_lines=200))
        assert result.high_complexity_count == 1
        assert result.models[0].is_high_complexity

    def test_join_counting(self) -> None:
        sql = "SELECT * FROM a JOIN b ON a.id = b.id LEFT JOIN c ON b.id = c.id"
        models = {"m1": _make_model(compiled_sql=sql)}
        result = analyze_complexity(models, {}, {})
        assert result.models[0].join_count == 2

    def test_cte_counting(self) -> None:
        sql = "WITH cte1 AS (SELECT 1), cte2 AS (SELECT 2) SELECT * FROM cte1"
        models = {"m1": _make_model(compiled_sql=sql)}
        result = analyze_complexity(models, {}, {})
        assert result.models[0].cte_count >= 1

    def test_subquery_counting(self) -> None:
        sql = "SELECT * FROM (SELECT id FROM t) sub WHERE id IN (SELECT id FROM u)"
        models = {"m1": _make_model(compiled_sql=sql)}
        result = analyze_complexity(models, {}, {})
        assert result.models[0].subquery_count == 2


class TestNaming:
    def test_compliant_staging(self) -> None:
        models = {"m1": _make_model(name="stg_orders", folder="models/staging")}
        result = check_naming(models)
        assert result.compliance_rate == 1.0
        assert len(result.violations) == 0

    def test_non_compliant_staging(self) -> None:
        models = {"m1": _make_model(name="orders", folder="models/staging")}
        result = check_naming(models)
        assert len(result.violations) == 1
        assert result.violations[0].layer == "staging"

    def test_compliant_marts(self) -> None:
        models = {
            "m1": _make_model(name="fct_orders", folder="models/marts"),
            "m2": _make_model(uid="m2", name="dim_customers", folder="models/marts"),
        }
        result = check_naming(models)
        assert result.compliance_rate == 1.0

    def test_non_compliant_marts(self) -> None:
        models = {"m1": _make_model(name="orders", folder="models/marts")}
        result = check_naming(models)
        assert len(result.violations) == 1

    def test_no_layer_detected(self) -> None:
        models = {"m1": _make_model(name="anything", folder="models/utils")}
        result = check_naming(models)
        assert result.total_checked == 0

    def test_custom_rules(self) -> None:
        rules = NamingRules(rules=(("staging", (r"^raw_",)),))
        models = {"m1": _make_model(name="raw_orders", folder="models/staging")}
        result = check_naming(models, rules)
        assert result.compliance_rate == 1.0

    def test_custom_layer_base_compliant(self) -> None:
        rules = NamingRules(
            rules=(
                ("base", (r"^base_",)),
                ("staging", (r"^stg_",)),
            )
        )
        models = {"m1": _make_model(name="base_orders", folder="models/base")}
        result = check_naming(models, rules)
        assert result.compliance_rate == 1.0
        assert len(result.violations) == 0

    def test_custom_layer_base_violation(self) -> None:
        rules = NamingRules(
            rules=(
                ("base", (r"^base_",)),
                ("staging", (r"^stg_",)),
            )
        )
        models = {"m1": _make_model(name="orders", folder="models/base")}
        result = check_naming(models, rules)
        assert len(result.violations) == 1
        assert result.violations[0].layer == "base"

    def test_base_model_in_staging_subfolder(self) -> None:
        """The bug scenario from issue #80: base_invoice in staging/base/ folder
        should detect as 'base' layer (first match in rule order), not 'staging'."""
        rules = NamingRules(
            rules=(
                ("base", (r"^base_",)),
                ("staging", (r"^stg_",)),
            )
        )
        models = {
            "m1": _make_model(
                name="base_invoice",
                folder="models/staging/base",
                path="models/staging/base/base_invoice.sql",
            )
        }
        result = check_naming(models, rules)
        assert result.compliance_rate == 1.0

    def test_layer_not_matched_when_no_folder_segment(self) -> None:
        """A layer named 'int' should NOT match a folder named 'internal'."""
        rules = NamingRules(rules=(("int", (r"^int_",)),))
        models = {"m1": _make_model(name="something", folder="models/internal")}
        result = check_naming(models, rules)
        assert result.total_checked == 0

    def test_windows_backslash_paths(self) -> None:
        """Paths normalized from Windows manifests should still detect layers."""
        rules = NamingRules(
            rules=(
                ("base", (r"^base_",)),
                ("staging", (r"^stg_",)),
            )
        )
        # After _get_folder normalizes backslashes, folder will be "models/billing/base"
        models = {
            "m1": _make_model(
                name="base_invoice",
                folder="models/billing/base",
                path="models/billing/base/base_invoice.sql",
            )
        }
        result = check_naming(models, rules)
        assert result.compliance_rate == 1.0


class TestHealthScore:
    def test_perfect_health(self) -> None:
        models = {
            "m1": _make_model(
                name="stg_orders",
                folder="models/staging",
                description="documented",
                columns=[{"name": "id", "description": "pk", "tests": [{"test_name": "t"}]}],
                test_results=[{"status": "pass"}],
                referenced_by=["m2"],
            ),
        }
        report = compute_health(models, {}, {}, {})
        assert report.score.overall > 80
        assert report.score.grade in ("A", "B")

    def test_poor_health(self) -> None:
        models = {
            "m1": _make_model(
                name="orders",
                folder="models/staging",
                columns=[{"name": "id", "description": "", "tests": []}],
            ),
            "m2": _make_model(
                uid="m2",
                name="revenue",
                folder="models/marts",
                columns=[{"name": "id", "description": "", "tests": []}],
            ),
        }
        report = compute_health(models, {}, {}, {})
        assert report.score.overall < 60
        assert report.score.documentation == 0.0
        assert report.score.testing == 0.0

    def test_health_to_dict(self) -> None:
        models = {"m1": _make_model(description="yes")}
        report = compute_health(models, {}, {}, {})
        data = health_to_dict(report)

        assert "score" in data
        assert "coverage" in data
        assert "complexity" in data
        assert "naming" in data
        assert "orphans" in data
        assert isinstance(data["score"]["overall"], float)
        assert data["score"]["grade"] in ("A", "B", "C", "D", "F")

    def test_orphan_detection(self) -> None:
        models = {
            "m1": _make_model(referenced_by=[]),
            "m2": _make_model(uid="m2", name="m2", referenced_by=["m1"]),
        }
        report = compute_health(models, {}, {}, {})
        orphan_ids = [o["unique_id"] for o in report.orphan_models]
        assert "m1" in orphan_ids
        assert "m2" not in orphan_ids

    def test_freshness_score_no_monitored_sources(self) -> None:
        """When no sources have freshness monitoring, freshness is N/A (0.0)
        and its weight is redistributed to other dimensions."""
        report = compute_health({}, {}, {}, {})
        assert report.score.freshness == 0.0

    def test_freshness_weight_excluded_when_not_applicable(self) -> None:
        """Overall score should not include freshness weight when no sources
        are monitored — scores should be higher than if freshness dragged
        them down, but not inflated by a free 100%."""
        models = {"m1": _make_model(description="documented", referenced_by=["m2"])}
        # With no monitored sources, freshness weight redistributed
        report_no_freshness = compute_health(models, {}, {}, {})
        # With passing freshness, freshness contributes normally
        sources = {"s1": _make_source(freshness_status="pass")}
        report_with_freshness = compute_health(models, sources, {}, {})
        # Both should produce similar overall scores since freshness=100%
        # in the monitored case and redistributed in the unmonitored case
        assert abs(report_no_freshness.score.overall - report_with_freshness.score.overall) < 20

    def test_freshness_score_with_sources(self) -> None:
        sources = {
            "s1": _make_source(freshness_status="pass"),
            "s2": _make_source(uid="s2", name="t2", freshness_status="warn"),
        }
        report = compute_health({}, sources, {}, {})
        assert 50 < report.score.freshness < 100


class TestHealthIntegration:
    """Test health with real fixture data via build_docglow_data."""

    def test_health_in_data_data(self, tmp_path):
        from pathlib import Path

        from docglow.artifacts.loader import load_artifacts
        from docglow.generator.data import build_docglow_data

        fixtures = Path(__file__).parent / "fixtures"
        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json", "run_results.json"):
            src = fixtures / name
            if src.exists():
                (target / name).write_text(src.read_text())

        artifacts = load_artifacts(tmp_path)
        data = build_docglow_data(artifacts)

        health = data["health"]
        assert "score" in health
        assert health["score"]["overall"] > 0
        assert health["score"]["grade"] in ("A", "B", "C", "D", "F")
        assert "coverage" in health
        assert "complexity" in health
