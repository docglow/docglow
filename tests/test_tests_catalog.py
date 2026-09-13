"""Tests for the project-wide test catalog (Tests dashboard payload)."""

from __future__ import annotations

import json
from pathlib import Path

from docglow.artifacts.manifest import Manifest
from docglow.artifacts.run_results import RunResults
from docglow.generator.transforms.lookups import build_run_results_map
from docglow.generator.transforms.tests import build_test_catalog

FIXTURES = Path(__file__).parent / "fixtures"


def _load() -> tuple[Manifest, RunResults]:
    manifest = Manifest.model_validate(json.loads((FIXTURES / "manifest.json").read_text()))
    run_results = RunResults.model_validate(json.loads((FIXTURES / "run_results.json").read_text()))
    return manifest, run_results


class TestBuildTestCatalog:
    def test_every_test_node_is_included(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)

        catalog = build_test_catalog(manifest, rr_map, has_run_results=True)

        expected = sum(1 for n in manifest.nodes.values() if n.resource_type == "test")
        assert len(catalog["tests"]) == expected
        assert catalog["summary"]["total"] == expected

    def test_entry_shape_and_status(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)

        catalog = build_test_catalog(manifest, rr_map, has_run_results=True)

        entry = catalog["tests"][0]
        assert set(entry) == {
            "unique_id",
            "name",
            "test_type",
            "is_generic",
            "column_name",
            "severity",
            "status",
            "failures",
            "execution_time",
            "message",
            "package_name",
            "original_file_path",
            "attached",
        }
        # Fixture run_results are all "success" -> normalized to "pass".
        assert all(t["status"] == "pass" for t in catalog["tests"])
        assert entry["severity"] in ("error", "warn")

    def test_generic_tests_carry_type_and_attachment(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)

        catalog = build_test_catalog(manifest, rr_map, has_run_results=True)

        not_null = [t for t in catalog["tests"] if t["test_type"] == "not_null"]
        assert not_null, "expected not_null tests in jaffle-shop fixture"
        sample = not_null[0]
        assert sample["is_generic"] is True
        assert sample["column_name"] is not None
        assert sample["attached"], "generic test should resolve its attached model"
        assert sample["attached"][0]["resource_type"] in ("model", "source", "seed", "snapshot")

    def test_summary_aggregates(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)

        summary = build_test_catalog(manifest, rr_map, has_run_results=True)["summary"]

        assert summary["has_run_results"] is True
        assert sum(summary["by_status"].values()) == summary["total"]
        assert sum(summary["by_severity"].values()) == summary["total"]
        assert sum(summary["by_type"].values()) == summary["total"]
        # All passing in the fixture.
        assert summary["pass_rate"] == 1.0
        assert summary["resources_tested"] > 0

    def test_without_run_results_all_not_run(self) -> None:
        manifest, _ = _load()

        catalog = build_test_catalog(manifest, {}, has_run_results=False)

        assert all(t["status"] == "not_run" for t in catalog["tests"])
        assert all(t["failures"] is None for t in catalog["tests"])
        summary = catalog["summary"]
        assert summary["has_run_results"] is False
        # No test ran -> pass rate is unknown, not a misleading 0 or 1.
        assert summary["pass_rate"] is None
        assert summary["by_status"]["not_run"] == summary["total"]

    def test_failing_tests_sort_first(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)
        # Force one test into a failing state.
        test_id = next(n.unique_id for n in manifest.nodes.values() if n.resource_type == "test")
        target = rr_map[test_id]
        target.status = "fail"
        target.failures = 3

        catalog = build_test_catalog(manifest, rr_map, has_run_results=True)

        assert catalog["tests"][0]["status"] == "fail"
        assert catalog["tests"][0]["failures"] == 3

    def test_warn_fail_error_are_surfaced(self) -> None:
        """The jaffle-shop fixture is all-passing, so synthesize the non-pass
        outcomes to lock in status normalization, ordering, failure/message
        passthrough, and how warns fold into the pass rate."""
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)
        test_ids = [n.unique_id for n in manifest.nodes.values() if n.resource_type == "test"]

        rr_map[test_ids[0]].status = "fail"
        rr_map[test_ids[0]].failures = 5
        rr_map[test_ids[0]].message = "Got 5 results, configured to fail if != 0"
        rr_map[test_ids[1]].status = "error"
        rr_map[test_ids[1]].message = "compilation error"
        # dbt reports a warn-severity breach as status "warn" (not "fail").
        rr_map[test_ids[2]].status = "warn"
        rr_map[test_ids[2]].failures = 2

        catalog = build_test_catalog(manifest, rr_map, has_run_results=True)
        tests = catalog["tests"]
        summary = catalog["summary"]

        # Ordering: fail, then error, then warn ahead of all the passes.
        assert [t["status"] for t in tests[:3]] == ["fail", "error", "warn"]
        assert tests[0]["failures"] == 5
        assert tests[0]["message"] == "Got 5 results, configured to fail if != 0"
        assert tests[1]["message"] == "compilation error"

        assert summary["by_status"]["fail"] == 1
        assert summary["by_status"]["error"] == 1
        assert summary["by_status"]["warn"] == 1
        # A warn counts as "did not fail": pass_rate excludes only fail/error.
        # 27 ran, 24 pass + 1 warn credited, 1 fail + 1 error excluded.
        assert summary["pass_rate"] == 25 / 27
