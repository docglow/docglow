"""Build the lineage graph (nodes + edges) from transformed model data."""

from __future__ import annotations

from typing import Any

from docglow.artifacts.manifest import Manifest
from docglow.generator.layers import LineageLayerConfig, layers_to_dict, resolve_all_layers


def build_lineage(
    manifest: Manifest,
    models: dict[str, Any],
    sources: dict[str, Any],
    seeds: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    layer_config: LineageLayerConfig,
    exclude_packages: bool = True,
) -> dict[str, Any]:
    """Build lineage graph nodes and edges."""
    # Determine which node IDs to exclude (package models/seeds/snapshots)
    excluded_ids: set[str] = set()
    if exclude_packages:
        for collection in (models, seeds, snapshots):
            for uid, data in collection.items():
                if data.get("is_package", False):
                    excluded_ids.add(uid)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()

    def _add_lineage_node(
        unique_id: str,
        name: str,
        resource_type: str,
        materialization: str,
        schema: str,
        test_status: str,
        has_description: bool,
        folder: str,
        tags: list[str],
        meta: dict[str, Any] | None = None,
    ) -> None:
        if unique_id in seen_node_ids:
            return
        seen_node_ids.add(unique_id)
        nodes.append(
            {
                "id": unique_id,
                "name": name,
                "resource_type": resource_type,
                "materialization": materialization,
                "schema": schema,
                "test_status": test_status,
                "has_description": has_description,
                "folder": folder,
                "tags": tags,
                "meta": meta or {},
            }
        )

    def _get_test_status(model_data: dict[str, Any]) -> str:
        test_results = model_data.get("test_results", [])
        if not test_results:
            return "none"
        statuses = {t["status"] for t in test_results}
        if "fail" in statuses or "error" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        if "pass" in statuses:
            return "pass"
        return "none"

    # Add model/seed/snapshot nodes
    for collection, resource_type in [
        (models, "model"),
        (seeds, "seed"),
        (snapshots, "snapshot"),
    ]:
        for uid, data in collection.items():
            if uid in excluded_ids:
                continue
            _add_lineage_node(
                unique_id=uid,
                name=data["name"],
                resource_type=resource_type,
                materialization=data.get("materialization", ""),
                schema=data.get("schema", ""),
                test_status=_get_test_status(data),
                has_description=bool(data.get("description")),
                folder=data.get("folder", ""),
                tags=data.get("tags", []),
                meta=data.get("meta", {}),
            )
            for dep in data.get("depends_on", []):
                if dep not in excluded_ids:
                    edges.append({"source": dep, "target": uid})

    # Add source nodes
    for uid, data in sources.items():
        _add_lineage_node(
            unique_id=uid,
            name=f"{data['source_name']}.{data['name']}",
            resource_type="source",
            materialization="",
            schema=data.get("schema", ""),
            test_status="none",
            has_description=bool(data.get("description")),
            folder="",
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
        )

    # Add exposure nodes from manifest
    for uid, exposure in manifest.exposures.items():
        _add_lineage_node(
            unique_id=uid,
            name=exposure.name,
            resource_type="exposure",
            materialization="",
            schema="",
            test_status="none",
            has_description=bool(exposure.description),
            folder="",
            tags=list(exposure.tags),
        )
        for dep in exposure.depends_on.nodes:
            if dep not in excluded_ids:
                edges.append({"source": dep, "target": uid})

    # Resolve layer ranks for all nodes
    layer_ranks, auto_assigned = resolve_all_layers(nodes, edges, layer_config)
    for node in nodes:
        node["layer"] = layer_ranks.get(node["id"])
        node["layer_auto"] = node["id"] in auto_assigned
        # Remove meta from lineage output (only needed for layer resolution)
        node.pop("meta", None)

    return {
        "nodes": nodes,
        "edges": edges,
        "layer_config": layers_to_dict(layer_config),
    }
