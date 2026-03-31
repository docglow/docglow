"""Build the search index for the frontend Fuse.js full-text search."""

from __future__ import annotations

from typing import Any


def build_search_index(
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the search index for Fuse.js.

    Emits two kinds of entries:
    - **resource entries** (model / source / seed / snapshot) — one per resource,
      with a comma-separated ``columns`` field for broad matching.
    - **column entries** — one per column per resource, enabling users to search
      for a column name and jump directly to the model + column.
    """
    entries: list[dict[str, Any]] = []

    for collection, resource_type in [
        (models, "model"),
        (sources, "source"),
        (seeds, "seed"),
        (snapshots, "snapshot"),
    ]:
        for uid, data in collection.items():
            columns = data.get("columns", [])
            column_names = [c["name"] for c in columns]
            sql = data.get("compiled_sql", "") or data.get("raw_sql", "")
            model_name = data.get("name", "")

            # Resource-level entry (existing behaviour)
            entries.append(
                {
                    "unique_id": uid,
                    "name": model_name,
                    "resource_type": resource_type,
                    "description": data.get("description", ""),
                    "columns": ", ".join(column_names),
                    "tags": ", ".join(data.get("tags", [])),
                    "sql_snippet": sql[:500],
                }
            )

            # Column-level entries — one per column
            for col in columns:
                col_name: str = col.get("name", "")
                if not col_name:
                    continue
                entries.append(
                    {
                        "unique_id": uid,
                        "name": col_name,
                        "resource_type": "column",
                        "column_name": col_name,
                        "model_name": model_name,
                        "description": col.get("description", ""),
                        "columns": "",
                        "tags": "",
                        "sql_snippet": "",
                    }
                )

    return entries
