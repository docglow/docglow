"""Build lookup maps from dbt artifacts for efficient cross-referencing."""

from __future__ import annotations

from docglow.artifacts.manifest import Manifest, ManifestNode
from docglow.artifacts.run_results import RunResult, RunResults


def build_run_results_map(
    run_results: RunResults | None,
) -> dict[str, RunResult]:
    """Map unique_id -> RunResult for quick lookup."""
    if run_results is None:
        return {}
    return {r.unique_id: r for r in run_results.results}


def build_test_map(
    manifest: Manifest,
) -> dict[str, list[ManifestNode]]:
    """Map model unique_id -> list of test nodes that depend on it."""
    test_map: dict[str, list[ManifestNode]] = {}
    for node in manifest.nodes.values():
        if node.resource_type != "test":
            continue
        for dep_id in node.depends_on.nodes:
            if dep_id not in test_map:
                test_map[dep_id] = []
            test_map[dep_id].append(node)
    return test_map


def build_reverse_dependency_map(manifest: Manifest) -> dict[str, list[str]]:
    """Build a map of unique_id -> list of unique_ids that depend on it."""
    if manifest.child_map:
        return dict(manifest.child_map)

    reverse: dict[str, list[str]] = {}
    for unique_id, node in manifest.nodes.items():
        if node.resource_type in ("test", "operation"):
            continue
        for dep_id in node.depends_on.nodes:
            if dep_id not in reverse:
                reverse[dep_id] = []
            reverse[dep_id].append(unique_id)
    return reverse
