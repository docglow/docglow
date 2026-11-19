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

# Fields that are often empty: unset when the test has no column, hasn't run,
# has no message (every pass), is singular (no attached node), or reads nothing
# beyond its attached node (most generic tests). Omitted from the wire format
# when empty to keep the payload proportional to what each test actually says.
_OMIT_WHEN_EMPTY = (
    "column_name",
    "failures",
    "execution_time",
    "message",
    "attached_node",
    "references",
)


def _compact(test: dict[str, Any]) -> dict[str, Any]:
    """Drop optional fields that are None or an empty list. ``0`` is kept."""
    return {
        key: value
        for key, value in test.items()
        if key not in _OMIT_WHEN_EMPTY or (value is not None and value != [])
    }


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


def _attached_node(node: ManifestNode) -> str | None:
    """The resource a test is defined on, per dbt's own ``attached_node``.

    Never inferred from ``depends_on.nodes``: its order is not meaningful
    (``relationships`` tests list the *referenced* model first). Singular tests
    have no attached node, because dbt assigns them none.
    """
    if node.attached_node and node.attached_node.startswith(_ATTACHABLE_PREFIXES):
        return node.attached_node
    return None


def _references(node: ManifestNode, attached_node: str | None) -> list[str]:
    """Other resources the test reads, deduped, in dbt order, excluding the attached node.

    For a ``relationships`` test this is the referenced (parent) model; for a
    singular test it is every model/source/seed/snapshot the SQL touches.
    """
    refs: list[str] = []
    for dep_id in node.depends_on.nodes:
        if dep_id == attached_node or dep_id in refs:
            continue
        if dep_id.startswith(_ATTACHABLE_PREFIXES):
            refs.append(dep_id)
    return refs


def _build_name_index(manifest: Manifest) -> dict[str, str]:
    """Map unique_id -> display name for models, seeds, snapshots, sources (sort key only)."""
    index = {uid: node.name for uid, node in manifest.nodes.items()}
    for uid, source in manifest.sources.items():
        index[uid] = f"{source.source_name}.{source.name}" if source.source_name else source.name
    return index


def _in_site(attached_node: str | None, references: list[str], resource_ids: set[str]) -> bool:
    """Whether a test belongs in a site that contains exactly ``resource_ids``.

    A test belongs where the resource it is defined on was generated. A singular
    test (no attached node) belongs when any resource it reads was generated,
    and a test that reads no resource at all can't dangle, so it is kept.
    """
    if attached_node:
        return attached_node in resource_ids
    return not references or any(ref in resource_ids for ref in references)


def build_test_catalog(
    manifest: Manifest,
    run_results_by_id: dict[str, RunResult],
    *,
    resource_ids: set[str],
    has_run_results: bool,
    generated_at: str = "",
) -> dict[str, Any]:
    """Build the project-wide ``tests`` payload: per-test list + summary.

    ``resource_ids`` is every model/seed/snapshot/source the site contains,
    i.e. what survived ``--select`` / ``--exclude``. Tests on anything else are
    dropped, and ``references`` is narrowed to it, so the payload never points
    at a page that was not generated. The summary is computed over what remains.

    ``has_run_results`` reflects whether a ``run_results.json`` was loaded at
    all; when ``False`` every test is reported as ``not_run`` and rate/severity
    outcomes are presented as unknown rather than as passing.
    """
    name_by_id = _build_name_index(manifest)

    tests: list[dict[str, Any]] = []
    for uid, node in manifest.nodes.items():
        if node.resource_type != "test":
            continue

        attached_node = _attached_node(node)
        all_references = _references(node, attached_node)
        if not _in_site(attached_node, all_references, resource_ids):
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
                # Whole milliseconds: all the UI ever shows (formatDuration), and
                # dbt's full float precision costs ~15 bytes per test.
                "execution_time": (round(result.execution_time, 3) if result else None),
                "message": (result.message if result else None),
                "package_name": node.package_name,
                "original_file_path": node.original_file_path,
                "attached_node": attached_node,
                "references": [ref for ref in all_references if ref in resource_ids],
            }
        )

    def primary_name(test: dict[str, Any]) -> str:
        primary = test["attached_node"] or next(iter(test["references"]), None)
        return name_by_id.get(primary, "~").lower() if primary else "~"

    # Stable ordering: failing first, then by the tested resource's name, then test name.
    status_rank = {status: i for i, status in enumerate(_STATUS_ORDER)}
    tests.sort(
        key=lambda t: (
            status_rank.get(t["status"], len(_STATUS_ORDER)),
            primary_name(t),
            t["name"].lower(),
        )
    )

    return {
        "tests": [_compact(test) for test in tests],
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
        # A resource counts as tested when a test is defined on it. A
        # relationships test's *referenced* model is read, not tested, so only
        # singular tests (which have no attached node) credit their references.
        if test["attached_node"]:
            tested_resources.add(test["attached_node"])
        else:
            tested_resources.update(test["references"])

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
