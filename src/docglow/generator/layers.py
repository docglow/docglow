"""Layer resolution for lineage graph ordering.

Assigns a numeric layer (rank) to each lineage node so that the graph
displays nodes in semantically meaningful horizontal positions
(e.g., sources → staging → intermediate → marts → exposures).

Resolution priority:
1. Explicit meta: ``meta.docglow.layer`` (string layer name or int rank)
2. Folder pattern matching
3. Tag matching (``layer:<name>``)
4. Name prefix/suffix matching
5. Resource type defaults (source/seed → 0, exposure → max rank)
6. Auto-assignment based on neighbor ranks
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayerDefinition:
    """A named layer with a rank and display color."""

    name: str
    rank: int
    color: str  # hex color for frontend band


@dataclass(frozen=True)
class LayerRule:
    """A rule that maps nodes to layers by pattern."""

    layer: str
    match_type: str  # "folder", "tag", "name_prefix", "name_suffix", "name_glob", "schema"
    pattern: str


DEFAULT_LAYERS: tuple[LayerDefinition, ...] = (
    LayerDefinition(name="source", rank=0, color="#dcfce7"),
    LayerDefinition(name="staging", rank=1, color="#dbeafe"),
    LayerDefinition(name="intermediate", rank=2, color="#fef3c7"),
    LayerDefinition(name="mart", rank=3, color="#fce7f3"),
    LayerDefinition(name="exposure", rank=4, color="#f3e8ff"),
)

DEFAULT_RULES: tuple[LayerRule, ...] = (
    # Folder-based rules
    LayerRule(layer="staging", match_type="folder", pattern="*staging*"),
    LayerRule(layer="staging", match_type="folder", pattern="*prep*"),
    LayerRule(layer="intermediate", match_type="folder", pattern="*intermediate*"),
    LayerRule(layer="mart", match_type="folder", pattern="*mart*"),
    # Name prefix rules
    LayerRule(layer="staging", match_type="name_prefix", pattern="stg_"),
    LayerRule(layer="intermediate", match_type="name_prefix", pattern="int_"),
    LayerRule(layer="mart", match_type="name_prefix", pattern="fct_"),
    LayerRule(layer="mart", match_type="name_prefix", pattern="dim_"),
    LayerRule(layer="mart", match_type="name_prefix", pattern="fact_"),
    LayerRule(layer="mart", match_type="name_prefix", pattern="mart_"),
    # Name suffix rules
    LayerRule(layer="staging", match_type="name_suffix", pattern="_prep"),
)


@dataclass(frozen=True)
class LineageLayerConfig:
    """Configuration for lineage layer ordering."""

    layers: tuple[LayerDefinition, ...] = DEFAULT_LAYERS
    rules: tuple[LayerRule, ...] = DEFAULT_RULES


def parse_layer_config(raw: dict[str, Any]) -> LineageLayerConfig:
    """Parse lineage layer config from a dict (from docglow.yml)."""
    layers_raw = raw.get("layers")
    rules_raw = raw.get("rules")

    if layers_raw is None and rules_raw is None:
        return LineageLayerConfig()

    layers = DEFAULT_LAYERS
    if layers_raw is not None:
        layers = tuple(
            LayerDefinition(
                name=l["name"],
                rank=l["rank"],
                color=l.get("color", "#e2e8f0"),
            )
            for l in layers_raw
            if isinstance(l, dict) and "name" in l and "rank" in l
        )

    rules = DEFAULT_RULES
    if rules_raw is not None:
        rules = tuple(
            LayerRule(
                layer=r["layer"],
                match_type=r["match"],
                pattern=r["pattern"],
            )
            for r in rules_raw
            if isinstance(r, dict) and "layer" in r and "match" in r and "pattern" in r
        )

    return LineageLayerConfig(layers=layers, rules=rules)


def _layer_name_to_rank(name: str, layers: tuple[LayerDefinition, ...]) -> int | None:
    """Look up a layer name and return its rank, or None if not found."""
    for layer in layers:
        if layer.name == name:
            return layer.rank
    return None


def resolve_node_layer(
    *,
    name: str,
    folder: str,
    tags: list[str],
    meta: dict[str, Any],
    resource_type: str,
    schema: str,
    config: LineageLayerConfig,
) -> int | None:
    """Resolve the layer rank for a single node.

    Returns the integer rank, or None if no rule matched.
    """
    # 1. Explicit meta: meta.docglow.layer
    docglow_meta = meta.get("docglow", {})
    if isinstance(docglow_meta, dict):
        layer_value = docglow_meta.get("layer")
        if layer_value is not None:
            if isinstance(layer_value, int):
                return layer_value
            if isinstance(layer_value, str):
                rank = _layer_name_to_rank(layer_value, config.layers)
                if rank is not None:
                    return rank
                logger.warning(
                    "Unknown layer name '%s' in meta for %s — ignoring",
                    layer_value,
                    name,
                )

    # 2–4. Apply rules in order (schema, folder, tag, name_prefix, name_suffix, name_glob)
    for rule in config.rules:
        matched = False

        if rule.match_type == "schema":
            matched = fnmatch.fnmatch(schema.lower(), rule.pattern.lower())
        elif rule.match_type == "folder":
            matched = fnmatch.fnmatch(folder.lower(), rule.pattern.lower())
        elif rule.match_type == "tag":
            matched = rule.pattern in tags
        elif rule.match_type == "name_prefix":
            matched = name.lower().startswith(rule.pattern.lower())
        elif rule.match_type == "name_suffix":
            matched = name.lower().endswith(rule.pattern.lower())
        elif rule.match_type == "name_glob":
            matched = fnmatch.fnmatch(name.lower(), rule.pattern.lower())

        if matched:
            rank = _layer_name_to_rank(rule.layer, config.layers)
            if rank is not None:
                return rank

    # 5. Resource type defaults
    if resource_type in ("source", "seed"):
        return _layer_name_to_rank("source", config.layers) or 0
    if resource_type == "exposure":
        max_rank = max((l.rank for l in config.layers), default=4)
        return max_rank

    return None


def resolve_all_layers(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    config: LineageLayerConfig,
) -> tuple[dict[str, int], set[str]]:
    """Resolve layer ranks for all nodes.

    Nodes that match no rule are auto-assigned based on neighbor ranks.
    Returns (node_id → rank mapping, set of auto-assigned node IDs).
    """
    result: dict[str, int] = {}
    unresolved: set[str] = set()

    # First pass: resolve all nodes that match rules
    for node in nodes:
        rank = resolve_node_layer(
            name=node["name"],
            folder=node.get("folder", ""),
            tags=node.get("tags", []),
            meta=node.get("meta", {}),
            resource_type=node["resource_type"],
            schema=node.get("schema", ""),
            config=config,
        )
        if rank is not None:
            result[node["id"]] = rank
        else:
            unresolved.add(node["id"])

    # Track which nodes were not directly matched by rules
    auto_assigned = set(unresolved)

    if not unresolved:
        return result, set()

    # Build adjacency for neighbor-based assignment
    upstream: dict[str, list[str]] = {}  # node_id → list of parent ids
    downstream: dict[str, list[str]] = {}  # node_id → list of child ids
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        downstream.setdefault(src, []).append(tgt)
        upstream.setdefault(tgt, []).append(src)

    # Iterative relaxation: assign unresolved nodes based on resolved neighbors
    for _ in range(3):
        if not unresolved:
            break
        newly_resolved: set[str] = set()

        for node_id in unresolved:
            neighbor_ranks: list[int] = []

            # Check upstream parents (they should have lower ranks)
            for parent in upstream.get(node_id, []):
                if parent in result:
                    neighbor_ranks.append(result[parent] + 1)

            # Check downstream children (they should have higher ranks)
            for child in downstream.get(node_id, []):
                if child in result:
                    neighbor_ranks.append(result[child] - 1)

            if neighbor_ranks:
                # Use the median of suggested ranks
                neighbor_ranks.sort()
                median = neighbor_ranks[len(neighbor_ranks) // 2]
                result[node_id] = max(0, median)
                newly_resolved.add(node_id)

        unresolved -= newly_resolved

    # Fallback: any still-unresolved nodes get the middle rank
    if unresolved:
        all_ranks = [l.rank for l in config.layers]
        middle = all_ranks[len(all_ranks) // 2] if all_ranks else 2
        for node_id in unresolved:
            result[node_id] = middle

    return result, auto_assigned


def layers_to_dict(config: LineageLayerConfig) -> list[dict[str, Any]]:
    """Convert layer definitions to a JSON-serializable list."""
    return [
        {"name": l.name, "rank": l.rank, "color": l.color}
        for l in config.layers
    ]
