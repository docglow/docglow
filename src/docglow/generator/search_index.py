"""Build the search index for the frontend Fuse.js full-text search."""

from __future__ import annotations

from typing import Any


def build_search_index(
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the search index for Fuse.js."""
    entries: list[dict[str, Any]] = []

    for collection, resource_type in [
        (models, "model"),
        (sources, "source"),
        (seeds, "seed"),
        (snapshots, "snapshot"),
    ]:
        for uid, data in collection.items():
            column_names = [c["name"] for c in data.get("columns", [])]
            sql = data.get("compiled_sql", "") or data.get("raw_sql", "")

            entries.append(
                {
                    "unique_id": uid,
                    "name": data.get("name", ""),
                    "resource_type": resource_type,
                    "description": data.get("description", ""),
                    "columns": ", ".join(column_names),
                    "tags": ", ".join(data.get("tags", [])),
                    "sql_snippet": sql[:500],
                }
            )

    return entries
