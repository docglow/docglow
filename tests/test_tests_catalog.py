"""Tests for the project-wide test catalog (Tests dashboard payload)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from docglow.artifacts.manifest import Manifest, ManifestNode
from docglow.artifacts.run_results import RunResults
from docglow.generator.transforms.lookups import build_run_results_map
from docglow.generator.transforms.tests import build_test_catalog

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_DIRS = [FIXTURES, FIXTURES / "dbt-1.8", FIXTURES / "dbt-1.9"]


def _load(fixture_dir: Path = FIXTURES) -> tuple[Manifest, RunResults]:
    manifest = Manifest.model_validate(json.loads((fixture_dir / "manifest.json").read_text()))
    run_results = RunResults.model_validate(
        json.loads((fixture_dir / "run_results.json").read_text())
    )
    return manifest, run_results


def _all_resources(manifest: Manifest) -> set[str]:
    """Every model/seed/snapshot/source: an unfiltered site."""
    nodes = {
        uid for uid, n in manifest.nodes.items() if n.resource_type in ("model", "seed", "snapshot")
    }
    return nodes | set(manifest.sources)


def _catalog(
    manifest: Manifest,
    run_results: RunResults | None = None,
    resource_ids: set[str] | None = None,
) -> dict[str, Any]:
    rr_map = build_run_results_map(run_results) if run_results else {}
    return build_test_catalog(
        manifest,
        rr_map,
        resource_ids=_all_resources(manifest) if resource_ids is None else resource_ids,
        has_run_results=run_results is not None,
    )


def _by_name(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["name"]: t for t in catalog["tests"]}


def _add_singular_test(manifest: Manifest, *deps: str) -> str:
    """Insert a singular (data) test reading ``deps``. No fixture has one."""
    uid = "test.jaffle_shop.assert_orders_match_supplies"
    manifest.nodes[uid] = ManifestNode.model_validate(
        {
            "unique_id": uid,
            "name": "assert_orders_match_supplies",
            "resource_type": "test",
            "package_name": "jaffle_shop",
            "original_file_path": "tests/assert_orders_match_supplies.sql",
            "depends_on": {"macros": [], "nodes": list(deps)},
            "attached_node": None,
        }
    )
    return uid


class TestBuildTestCatalog:
    def test_every_test_node_is_included(self) -> None:
        manifest, run_results = _load()

        catalog = _catalog(manifest, run_results)

        expected = sum(1 for n in manifest.nodes.values() if n.resource_type == "test")
        assert len(catalog["tests"]) == expected
        assert catalog["summary"]["total"] == expected

    def test_entry_shape_and_status(self) -> None:
        manifest, run_results = _load()

        catalog = _catalog(manifest, run_results)

        required = {
            "unique_id",
            "name",
            "test_type",
            "is_generic",
            "severity",
            "status",
            "package_name",
            "original_file_path",
        }
        optional = {
            "column_name",
            "failures",
            "execution_time",
            "message",
            "attached_node",
            "references",
        }
        for test in catalog["tests"]:
            assert required <= set(test) <= required | optional, test["name"]
            # Optional fields are omitted when empty, never sent as null / [].
            assert all(test[k] is not None and test[k] != [] for k in optional & set(test))
        entry = catalog["tests"][0]
        # Fixture run_results are all "success" -> normalized to "pass".
        assert all(t["status"] == "pass" for t in catalog["tests"])
        assert entry["severity"] in ("error", "warn")

    def test_summary_aggregates(self) -> None:
        manifest, run_results = _load()

        summary = _catalog(manifest, run_results)["summary"]

        assert summary["has_run_results"] is True
        assert sum(summary["by_status"].values()) == summary["total"]
        assert sum(summary["by_severity"].values()) == summary["total"]
        assert sum(summary["by_type"].values()) == summary["total"]
        # All passing in the fixture.
        assert summary["pass_rate"] == 1.0
        # Distinct resources with a test defined on them, per attached_node.
        attached = {n.attached_node for n in manifest.nodes.values() if n.resource_type == "test"}
        assert summary["resources_tested"] == len(attached)

    def test_without_run_results_all_not_run(self) -> None:
        manifest, _ = _load()

        catalog = _catalog(manifest)

        assert all(t["status"] == "not_run" for t in catalog["tests"])
        # Nothing ran, so no test carries run-derived fields at all.
        assert all("failures" not in t and "execution_time" not in t for t in catalog["tests"])
        summary = catalog["summary"]
        assert summary["has_run_results"] is False
        # No test ran -> pass rate is unknown, not a misleading 0 or 1.
        assert summary["pass_rate"] is None
        assert summary["by_status"]["not_run"] == summary["total"]

    def test_execution_time_is_rounded_to_milliseconds(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)
        test_id = next(n.unique_id for n in manifest.nodes.values() if n.resource_type == "test")
        rr_map[test_id].execution_time = 0.009351968765258789

        catalog = build_test_catalog(
            manifest, rr_map, resource_ids=_all_resources(manifest), has_run_results=True
        )

        test = next(t for t in catalog["tests"] if t["unique_id"] == test_id)
        assert test["execution_time"] == 0.009

    def test_failing_tests_sort_first(self) -> None:
        manifest, run_results = _load()
        rr_map = build_run_results_map(run_results)
        # Force one test into a failing state.
        test_id = next(n.unique_id for n in manifest.nodes.values() if n.resource_type == "test")
        target = rr_map[test_id]
        target.status = "fail"
        target.failures = 3

        catalog = build_test_catalog(
            manifest, rr_map, resource_ids=_all_resources(manifest), has_run_results=True
        )

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

        catalog = build_test_catalog(
            manifest, rr_map, resource_ids=_all_resources(manifest), has_run_results=True
        )
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


class TestAttribution:
    """A test belongs to dbt's ``attached_node``, never to ``depends_on.nodes[0]``."""

    @pytest.mark.parametrize("fixture_dir", FIXTURE_DIRS, ids=lambda p: p.name)
    def test_attached_node_matches_manifest_for_every_test(self, fixture_dir: Path) -> None:
        manifest, run_results = _load(fixture_dir)

        catalog = _catalog(manifest, run_results)

        for test in catalog["tests"]:
            node = manifest.nodes[test["unique_id"]]
            assert test.get("attached_node") == node.attached_node, test["name"]
            assert test.get("attached_node") not in test.get("references", []), test["name"]

    # One hand-verified instance of each generic test type in the fixture,
    # checked against the raw manifest and the YAML that defines it.
    @pytest.mark.parametrize(
        ("name", "attached_node", "references"),
        [
            (
                "accepted_values_customers_customer_type__new__returning",
                "model.jaffle_shop.customers",
                [],
            ),
            (
                "dbt_utils_expression_is_true_customers_lifetime_spend_pretax_lifetime_tax_paid_lifetime_spend",
                "model.jaffle_shop.customers",
                [],
            ),
            ("not_null_customers_customer_id", "model.jaffle_shop.customers", []),
            ("unique_customers_customer_id", "model.jaffle_shop.customers", []),
            # dbt lists the referenced model first in depends_on.nodes:
            # ['model.jaffle_shop.stg_customers', 'model.jaffle_shop.orders'].
            (
                "relationships_orders_customer_id__customer_id__ref_stg_customers_",
                "model.jaffle_shop.orders",
                ["model.jaffle_shop.stg_customers"],
            ),
            (
                "relationships_order_items_order_id__order_id__ref_orders_",
                "model.jaffle_shop.order_items",
                ["model.jaffle_shop.orders"],
            ),
        ],
    )
    @pytest.mark.parametrize("fixture_dir", FIXTURE_DIRS, ids=lambda p: p.name)
    def test_each_test_type_attributes_correctly(
        self, fixture_dir: Path, name: str, attached_node: str, references: list[str]
    ) -> None:
        manifest, run_results = _load(fixture_dir)

        test = _by_name(_catalog(manifest, run_results))[name]

        assert test.get("attached_node") == attached_node
        assert test.get("references", []) == references

    def test_relationships_target_is_not_counted_as_tested(self) -> None:
        manifest, run_results = _load()
        # Keep only the orders -> stg_customers relationships test.
        manifest.nodes = {
            uid: n
            for uid, n in manifest.nodes.items()
            if n.resource_type != "test"
            or n.name == "relationships_orders_customer_id__customer_id__ref_stg_customers_"
        }

        summary = _catalog(manifest, run_results)["summary"]

        assert summary["resources_tested"] == 1  # orders, not stg_customers

    def test_singular_test_has_no_primary_and_references_every_resource(self) -> None:
        manifest, _ = _load()
        uid = _add_singular_test(
            manifest,
            "model.jaffle_shop.orders",
            "model.jaffle_shop.stg_supplies",
            "model.jaffle_shop.orders",  # duplicates are collapsed
        )

        test = next(t for t in _catalog(manifest)["tests"] if t["unique_id"] == uid)

        assert test["test_type"] == "singular"
        assert test["is_generic"] is False
        assert "attached_node" not in test  # omitted, not null
        assert test["references"] == [
            "model.jaffle_shop.orders",
            "model.jaffle_shop.stg_supplies",
        ]


ORDERS = "model.jaffle_shop.orders"
STG_CUSTOMERS = "model.jaffle_shop.stg_customers"
STG_SUPPLIES = "model.jaffle_shop.stg_supplies"
REL_ORDERS = "relationships_orders_customer_id__customer_id__ref_stg_customers_"


class TestSiteFiltering:
    """``resource_ids`` (what --select/--exclude kept) bounds every test and id."""

    def test_tests_on_resources_outside_the_site_are_dropped(self) -> None:
        manifest, run_results = _load()

        catalog = _catalog(manifest, run_results, resource_ids={ORDERS})

        expected = {
            n.name
            for n in manifest.nodes.values()
            if n.resource_type == "test" and n.attached_node == ORDERS
        }
        assert {t["name"] for t in catalog["tests"]} == expected
        assert catalog["summary"]["total"] == len(expected)
        assert catalog["summary"]["resources_tested"] == 1

    def test_reference_outside_the_site_is_dropped_but_the_test_stays(self) -> None:
        manifest, run_results = _load()

        # orders is generated; the relationships target stg_customers is not.
        test = _by_name(_catalog(manifest, run_results, resource_ids={ORDERS}))[REL_ORDERS]

        assert test["attached_node"] == ORDERS
        assert "references" not in test

    def test_test_whose_resource_is_filtered_out_is_dropped_even_if_it_references_the_site(
        self,
    ) -> None:
        manifest, run_results = _load()

        # stg_customers is generated, but this test is defined on orders.
        names = _by_name(_catalog(manifest, run_results, resource_ids={STG_CUSTOMERS}))

        assert REL_ORDERS not in names

    def test_singular_test_kept_when_any_resource_is_in_the_site(self) -> None:
        manifest, _ = _load()
        uid = _add_singular_test(manifest, ORDERS, STG_SUPPLIES)

        kept = _catalog(manifest, resource_ids={STG_SUPPLIES})["tests"]
        dropped = _catalog(manifest, resource_ids={STG_CUSTOMERS})["tests"]

        singular = next(t for t in kept if t["unique_id"] == uid)
        assert singular["references"] == [STG_SUPPLIES]
        assert all(t["unique_id"] != uid for t in dropped)


class TestPipelineHonorsSelection:
    """Through build_docglow_data, the way `docglow generate --select` runs it."""

    @staticmethod
    def _generate(tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
        import shutil

        from docglow.artifacts.loader import load_artifacts
        from docglow.generator.data import build_docglow_data

        target = tmp_path / "target"
        target.mkdir()
        for name in ("manifest.json", "catalog.json", "run_results.json"):
            shutil.copy(FIXTURES / name, target / name)
        return build_docglow_data(load_artifacts(tmp_path), **kwargs)

    @staticmethod
    def _assert_no_dangling_ids(data: dict[str, Any]) -> None:
        site = {**data["models"], **data["seeds"], **data["snapshots"], **data["sources"]}
        for test in data["tests"]["tests"]:
            if "attached_node" in test:
                assert test["attached_node"] in site, test["name"]
            for ref in test.get("references", []):
                assert ref in site, (test["name"], ref)

    def test_select_keeps_only_tests_on_generated_resources(self, tmp_path: Path) -> None:
        data = self._generate(tmp_path, select="stg_customers")

        assert set(data["models"]) == {STG_CUSTOMERS}
        self._assert_no_dangling_ids(data)
        manifest, _ = _load()
        site = {STG_CUSTOMERS} | set(manifest.sources)
        expected = sum(
            1
            for n in manifest.nodes.values()
            if n.resource_type == "test" and n.attached_node in site
        )
        assert data["tests"]["summary"]["total"] == expected
        assert len(data["tests"]["tests"]) == expected

    def test_exclude_drops_tests_on_excluded_resources(self, tmp_path: Path) -> None:
        data = self._generate(tmp_path, exclude="orders")

        assert ORDERS not in data["models"]
        self._assert_no_dangling_ids(data)
        assert all(t.get("attached_node") != ORDERS for t in data["tests"]["tests"])
        # order_items -> orders loses its now-missing reference but stays.
        rel = _by_name(data["tests"])["relationships_order_items_order_id__order_id__ref_orders_"]
        assert "references" not in rel

    def test_unfiltered_site_keeps_every_test(self, tmp_path: Path) -> None:
        data = self._generate(tmp_path)

        manifest, _ = _load()
        self._assert_no_dangling_ids(data)
        assert data["tests"]["summary"]["total"] == sum(
            1 for n in manifest.nodes.values() if n.resource_type == "test"
        )
