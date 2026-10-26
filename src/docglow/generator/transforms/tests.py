"""Build a project-wide catalog of dbt tests and their latest results.

This powers the Tests dashboard — an Elementary-style view built solely from
the local project's ``manifest.json`` and (optionally) ``run_results.json``.
There is no warehouse persistence and no run history: the payload reflects a
single point in time, the most recent ``dbt test`` / ``dbt build``.
"""

from __future__ import annotations

from typing import Any

from docglow.artifacts.manifest import Manifest, ManifestNode
from docglow.artifacts.run_results import RunResult
from docglow.generator.transforms.lookups import normalize_test_status

# Statuses we surface, in the order the dashboard displays them.
_STATUS_ORDER = ("fail", "error", "warn", "pass", "not_run")

# dbt resource-type prefixes a test can be attached to (i.e. what it validates).
_ATTACHABLE_PREFIXES = ("model.", "source.", "seed.", "snapshot.")


def _severity(node: ManifestNode) -> str:
    """Return the test's configured severity, normalized to error|warn.

    dbt stores severity at ``config.severity`` (default ``ERROR``). ``NodeConfig``
    allows extra fields, so it is read defensively.
    """
    raw = getattr(node.config, "severity", None)
    if not isinstance(raw, str) or not raw:
        return "error"
    lowered = raw.lower()
    return "warn" if lowered in ("warn", "warning") else "error"


def _attached_nodes(
    node: ManifestNode,
    name_by_id: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Resolve the models/sources a test validates, deduped and named."""
    attached: list[dict[str, str]] = []
    seen: set[str] = set()
    for dep_id in node.depends_on.nodes:
        if dep_id in seen or not dep_id.startswith(_ATTACHABLE_PREFIXES):
            continue
        seen.add(dep_id)
        info = name_by_id.get(dep_id)
        if info is None:
            continue
        attached.append(
            {
                "unique_id": dep_id,
                "name": info["name"],
                "resource_type": info["resource_type"],
            }
        )
    return attached


def _build_name_index(manifest: Manifest) -> dict[str, dict[str, str]]:
    """Map unique_id -> {name, resource_type} for models, seeds, snapshots, sources."""
    index: dict[str, dict[str, str]] = {}
    for uid, node in manifest.nodes.items():
        index[uid] = {"name": node.name, "resource_type": node.resource_type}
    for uid, source in manifest.sources.items():
        display = f"{source.source_name}.{source.name}" if source.source_name else source.name
        index[uid] = {"name": display, "resource_type": "source"}
    return index


def build_test_catalog(
    manifest: Manifest,
    run_results_by_id: dict[str, RunResult],
    *,
    has_run_results: bool,
    generated_at: str = "",
) -> dict[str, Any]:
    """Build the project-wide ``tests`` payload: per-test list + summary.

    ``has_run_results`` reflects whether a ``run_results.json`` was loaded at
    all; when ``False`` every test is reported as ``not_run`` and rate/severity
    outcomes are presented as unknown rather than as passing.
    """
    name_by_id = _build_name_index(manifest)

    tests: list[dict[str, Any]] = []
    for uid, node in manifest.nodes.items():
        if node.resource_type != "test":
            continue

        is_generic = node.test_metadata is not None
        test_type = node.test_metadata.name if node.test_metadata else "singular"

        result = run_results_by_id.get(uid)
        status = normalize_test_status(result.status) if result else "not_run"

        tests.append(
            {
                "unique_id": uid,
                "name": node.name,
                "test_type": test_type,
                "is_generic": is_generic,
                "column_name": node.column_name,
                "severity": _severity(node),
                "status": status,
                "failures": (result.failures if result else None),
                "execution_time": (result.execution_time if result else None),
                "message": (result.message if result else None),
                "package_name": node.package_name,
                "original_file_path": node.original_file_path,
                "attached": _attached_nodes(node, name_by_id),
            }
        )

    # Stable ordering: failing first, then by attached model name, then test name.
    status_rank = {status: i for i, status in enumerate(_STATUS_ORDER)}
    tests.sort(
        key=lambda t: (
            status_rank.get(t["status"], len(_STATUS_ORDER)),
            (t["attached"][0]["name"].lower() if t["attached"] else "~"),
            t["name"].lower(),
        )
    )

    return {
        "tests": tests,
        "summary": _build_summary(tests, has_run_results, generated_at),
    }


def _build_summary(
    tests: list[dict[str, Any]],
    has_run_results: bool,
    generated_at: str,
) -> dict[str, Any]:
    """Aggregate counts, pass rate, and coverage across all tests."""
    total = len(tests)

    by_status = {status: 0 for status in _STATUS_ORDER}
    by_severity = {"error": 0, "warn": 0}
    by_type: dict[str, int] = {}
    tested_resources: set[str] = set()

    for test in tests:
        by_status[test["status"]] = by_status.get(test["status"], 0) + 1
        by_severity[test["severity"]] = by_severity.get(test["severity"], 0) + 1
        by_type[test["test_type"]] = by_type.get(test["test_type"], 0) + 1
        for attached in test["attached"]:
            tested_resources.add(attached["unique_id"])

    ran = total - by_status["not_run"]
    # Pass rate is a fraction of tests that actually ran (warn counts as a pass
    # for the purpose of "did it block the build"). Unknown when nothing ran.
    pass_rate = (by_status["pass"] + by_status["warn"]) / ran if ran else None

    return {
        "has_run_results": has_run_results,
        "generated_at": generated_at,
        "total": total,
        "by_status": by_status,
        "by_severity": by_severity,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))),
        "pass_rate": pass_rate,
        "resources_tested": len(tested_resources),
    }
