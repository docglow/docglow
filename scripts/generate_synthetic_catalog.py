"""Generate a synthetic catalog.json from a dbt manifest.json.

Extracts column definitions, schema info, and materialization metadata
from the manifest to build a catalog that docglow can consume, without
needing a live database connection.

Usage:
    python scripts/generate_synthetic_catalog.py /path/to/dbt/project
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Snowflake-style type inference from column names and data_type hints
TYPE_HINTS: dict[str, str] = {
    "id": "VARCHAR",
    "uuid": "VARCHAR",
    "key": "VARCHAR",
    "name": "VARCHAR",
    "title": "VARCHAR",
    "description": "VARCHAR",
    "text": "VARCHAR",
    "label": "VARCHAR",
    "slug": "VARCHAR",
    "email": "VARCHAR",
    "url": "VARCHAR",
    "path": "VARCHAR",
    "type": "VARCHAR",
    "status": "VARCHAR",
    "code": "VARCHAR",
    "address": "VARCHAR",
    "phone": "VARCHAR",
    "date": "DATE",
    "created_at": "TIMESTAMP_NTZ",
    "updated_at": "TIMESTAMP_NTZ",
    "deleted_at": "TIMESTAMP_NTZ",
    "started_at": "TIMESTAMP_NTZ",
    "ended_at": "TIMESTAMP_NTZ",
    "timestamp": "TIMESTAMP_NTZ",
    "count": "NUMBER",
    "amount": "NUMBER(38,2)",
    "total": "NUMBER(38,2)",
    "price": "NUMBER(38,2)",
    "cost": "NUMBER(38,2)",
    "rate": "FLOAT",
    "ratio": "FLOAT",
    "percent": "FLOAT",
    "percentage": "FLOAT",
    "score": "FLOAT",
    "weight": "FLOAT",
    "is_": "BOOLEAN",
    "has_": "BOOLEAN",
    "flag": "BOOLEAN",
    "enabled": "BOOLEAN",
    "active": "BOOLEAN",
}


def infer_type(col_name: str, data_type: str | None) -> str:
    """Infer a plausible Snowflake column type from name and manifest hints."""
    if data_type:
        return data_type.upper()

    lower = col_name.lower()

    # Check exact matches first
    for pattern, typ in TYPE_HINTS.items():
        if lower == pattern or lower.endswith(f"_{pattern}"):
            return typ

    # Check prefix matches (is_, has_)
    if lower.startswith("is_") or lower.startswith("has_"):
        return "BOOLEAN"

    # Check suffix patterns
    if lower.endswith("_id") or lower.endswith("_uuid") or lower.endswith("_key"):
        return "VARCHAR"
    if lower.endswith("_at") or lower.endswith("_date") or lower.endswith("_time"):
        return "TIMESTAMP_NTZ"
    if lower.endswith("_count") or lower.endswith("_number") or lower.endswith("_num"):
        return "NUMBER"
    if lower.endswith("_amount") or lower.endswith("_total") or lower.endswith("_price") or lower.endswith("_cost"):
        return "NUMBER(38,2)"
    if lower.endswith("_rate") or lower.endswith("_ratio") or lower.endswith("_percent"):
        return "FLOAT"

    return "VARCHAR"


def materialization_to_table_type(materialization: str) -> str:
    """Map dbt materialization to catalog table type."""
    mapping = {
        "table": "BASE TABLE",
        "incremental": "BASE TABLE",
        "view": "VIEW",
        "ephemeral": "EPHEMERAL",
        "seed": "BASE TABLE",
        "snapshot": "BASE TABLE",
    }
    return mapping.get(materialization, "BASE TABLE")


def build_catalog_node(unique_id: str, node: dict) -> dict:
    """Build a catalog entry for a model/seed/snapshot node."""
    columns = {}
    manifest_cols = node.get("columns", {})

    for idx, (col_name, col_def) in enumerate(manifest_cols.items(), start=1):
        columns[col_name] = {
            "type": infer_type(col_name, col_def.get("data_type")),
            "index": idx,
            "name": col_name,
            "comment": col_def.get("description") or None,
        }

    materialization = node.get("config", {}).get("materialized", "table")

    return {
        "metadata": {
            "type": materialization_to_table_type(materialization),
            "schema": node.get("schema", ""),
            "name": node.get("alias") or node.get("name", ""),
            "database": node.get("database", ""),
            "comment": node.get("description") or None,
            "owner": None,
        },
        "columns": columns,
        "stats": {
            "has_stats": {
                "id": "has_stats",
                "label": "Has Stats?",
                "value": False,
                "include": False,
                "description": "Indicates whether there are statistics for this table",
            }
        },
        "unique_id": unique_id,
    }


def build_catalog_source(unique_id: str, source: dict) -> dict:
    """Build a catalog entry for a source node."""
    columns = {}
    manifest_cols = source.get("columns", {})

    for idx, (col_name, col_def) in enumerate(manifest_cols.items(), start=1):
        columns[col_name] = {
            "type": infer_type(col_name, col_def.get("data_type")),
            "index": idx,
            "name": col_name,
            "comment": col_def.get("description") or None,
        }

    return {
        "metadata": {
            "type": "BASE TABLE",
            "schema": source.get("schema", ""),
            "name": source.get("identifier") or source.get("name", ""),
            "database": source.get("database", ""),
            "comment": source.get("description") or None,
            "owner": None,
        },
        "columns": columns,
        "stats": {
            "has_stats": {
                "id": "has_stats",
                "label": "Has Stats?",
                "value": False,
                "include": False,
                "description": "Indicates whether there are statistics for this table",
            }
        },
        "unique_id": unique_id,
    }


def generate_catalog(manifest_path: Path) -> dict:
    """Generate a synthetic catalog from a manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    dbt_version = manifest.get("metadata", {}).get("dbt_version", "1.0.0")
    now = datetime.now(timezone.utc).isoformat()

    catalog_nodes = {}
    catalog_sources = {}

    # Process models, seeds, snapshots
    for unique_id, node in manifest.get("nodes", {}).items():
        resource_type = node.get("resource_type", "")
        if resource_type in ("model", "seed", "snapshot"):
            catalog_nodes[unique_id] = build_catalog_node(unique_id, node)

    # Process sources
    for unique_id, source in manifest.get("sources", {}).items():
        catalog_sources[unique_id] = build_catalog_source(unique_id, source)

    nodes_with_cols = sum(1 for n in catalog_nodes.values() if n["columns"])
    sources_with_cols = sum(1 for s in catalog_sources.values() if s["columns"])

    print(f"Generated catalog:")
    print(f"  Nodes: {len(catalog_nodes)} ({nodes_with_cols} with columns)")
    print(f"  Sources: {len(catalog_sources)} ({sources_with_cols} with columns)")

    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json",
            "dbt_version": dbt_version,
            "generated_at": now,
            "invocation_id": "synthetic-catalog",
            "invocation_started_at": now,
            "env": {},
        },
        "nodes": catalog_nodes,
        "sources": catalog_sources,
        "errors": None,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python generate_synthetic_catalog.py /path/to/dbt/project")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    manifest_path = project_dir / "target" / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: manifest.json not found at {manifest_path}")
        sys.exit(1)

    catalog = generate_catalog(manifest_path)

    output_path = project_dir / "target" / "catalog.json"
    output_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"  Written to: {output_path}")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
