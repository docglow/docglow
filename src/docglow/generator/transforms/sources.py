"""Transform dbt manifest sources into Docglow source dicts."""

from __future__ import annotations

from typing import Any

from docglow.artifacts.catalog import Catalog
from docglow.artifacts.manifest import ManifestSource


def transform_source(
    source: ManifestSource,
    catalog: Catalog,
    source_freshness: Any | None,
) -> dict[str, Any]:
    """Transform a manifest source into a DocglowSource dict."""
    catalog_node = catalog.sources.get(source.unique_id)

    # Merge columns
    catalog_columns: dict[str, Any] = {}
    if catalog_node and catalog_node.columns:
        catalog_columns = catalog_node.columns

    columns: list[dict[str, Any]] = []
    seen: set[str] = set()

    sorted_catalog = sorted(catalog_columns.values(), key=lambda c: c.index)
    for col in sorted_catalog:
        lower_name = col.name.lower()
        if lower_name not in seen:
            manifest_col = source.columns.get(col.name) or source.columns.get(col.name.lower())
            columns.append(
                {
                    "name": col.name,
                    "description": manifest_col.description if manifest_col else "",
                    "data_type": col.type if hasattr(col, "type") else "",
                    "meta": dict(manifest_col.meta) if manifest_col else {},
                    "tags": list(manifest_col.tags) if manifest_col else [],
                    "tests": [],
                    "profile": None,
                }
            )
            seen.add(lower_name)

    # Freshness info
    freshness_status = None
    freshness_max_loaded_at = None
    freshness_snapshotted_at = None

    if source_freshness:
        for fr in source_freshness.results:
            if fr.unique_id == source.unique_id:
                freshness_status = fr.status
                freshness_max_loaded_at = fr.max_loaded_at
                freshness_snapshotted_at = fr.snapshotted_at
                break

    return {
        "unique_id": source.unique_id,
        "name": source.name,
        "source_name": source.source_name,
        "description": source.description or source.source_description,
        "schema": source.schema_ or "",
        "database": source.database or "",
        "columns": columns,
        "tags": list(source.tags),
        "meta": dict(source.meta),
        "loader": source.loader,
        "loaded_at_field": source.loaded_at_field,
        "freshness_status": freshness_status,
        "freshness_max_loaded_at": freshness_max_loaded_at,
        "freshness_snapshotted_at": freshness_snapshotted_at,
    }
