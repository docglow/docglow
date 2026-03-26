"""Resource filtering for --select and --exclude patterns."""

from __future__ import annotations

import fnmatch
from typing import Any


def filter_resources(
    models: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    select: str | None = None,
    exclude: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Filter models/seeds/snapshots by --select and --exclude patterns.

    Supports:
      - Glob patterns matching model name: ``stg_*``, ``*orders*``
      - Folder paths: ``staging/*``, ``marts/finance/*``
      - ``+name`` prefix: include all upstream dependencies
      - ``name+`` suffix: include all downstream dependents
    """
    all_resources = {**models, **seeds, **snapshots}

    if select:
        selected = resolve_selection(select, all_resources)
    else:
        selected = set(all_resources.keys())

    if exclude:
        excluded = resolve_selection(exclude, all_resources)
        selected -= excluded

    return (
        {k: v for k, v in models.items() if k in selected},
        {k: v for k, v in seeds.items() if k in selected},
        {k: v for k, v in snapshots.items() if k in selected},
    )


def resolve_selection(
    pattern: str,
    resources: dict[str, Any],
) -> set[str]:
    """Resolve a selection pattern to a set of unique_ids."""
    include_upstream = pattern.startswith("+")
    include_downstream = pattern.endswith("+")
    clean = pattern.strip("+")

    matched: set[str] = set()
    for uid, data in resources.items():
        name = data.get("name", "")
        folder = data.get("folder", "")
        path = data.get("path", "")

        matches_filter = (
            fnmatch.fnmatch(name, clean)
            or fnmatch.fnmatch(folder, clean)
            or fnmatch.fnmatch(path, clean)
        )
        if matches_filter:
            matched.add(uid)

    if include_upstream:
        upstream: set[str] = set()
        for uid in matched:
            collect_upstream(uid, resources, upstream)
        matched |= upstream

    if include_downstream:
        downstream: set[str] = set()
        for uid in matched:
            collect_downstream(uid, resources, downstream)
        matched |= downstream

    return matched


def collect_upstream(
    uid: str,
    resources: dict[str, Any],
    visited: set[str],
) -> None:
    """Recursively collect upstream dependencies."""
    data = resources.get(uid)
    if not data:
        return
    for dep in data.get("depends_on", []):
        if dep not in visited and dep in resources:
            visited.add(dep)
            collect_upstream(dep, resources, visited)


def collect_downstream(
    uid: str,
    resources: dict[str, Any],
    visited: set[str],
) -> None:
    """Recursively collect downstream dependents."""
    data = resources.get(uid)
    if not data:
        return
    for ref in data.get("referenced_by", []):
        if ref not in visited and ref in resources:
            visited.add(ref)
            collect_downstream(ref, resources, visited)
