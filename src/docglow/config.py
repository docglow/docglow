"""Configuration management for docglow."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docglow.generator.layers import LineageLayerConfig, parse_layer_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfilingConfig:
    enabled: bool = False
    sample_size: int = 10000
    cache: bool = True
    exclude_schemas: tuple[str, ...] = ()
    top_values_threshold: int = 50


@dataclass(frozen=True)
class HealthWeights:
    documentation: float = 0.25
    testing: float = 0.25
    freshness: float = 0.15
    complexity: float = 0.15
    naming: float = 0.10
    orphans: float = 0.10


@dataclass(frozen=True)
class NamingRules:
    """Layer-name → regex-pattern mapping for naming compliance.

    Each entry is (layer_name, (pattern1, pattern2, ...)).
    A model in a folder matching the layer name must match at least one pattern.
    """

    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("staging", (r"^stg_",)),
        ("intermediate", (r"^int_",)),
        ("marts", (r"^fct_", r"^dim_")),
    )

    def layers(self) -> tuple[str, ...]:
        """Return all layer names in rule order."""
        return tuple(name for name, _ in self.rules)

    def patterns_for(self, layer: str) -> tuple[str, ...] | None:
        """Return the patterns for a layer, or None if not defined."""
        for name, patterns in self.rules:
            if name == layer:
                return patterns
        return None


@dataclass(frozen=True)
class ComplexityThresholds:
    high_sql_lines: int = 200
    high_join_count: int = 8
    high_cte_count: int = 10
    high_subquery_count: int = 5


@dataclass(frozen=True)
class HealthConfig:
    weights: HealthWeights = field(default_factory=HealthWeights)
    naming_rules: NamingRules = field(default_factory=NamingRules)
    complexity: ComplexityThresholds = field(default_factory=ComplexityThresholds)


@dataclass(frozen=True)
class AiConfig:
    enabled: bool = False
    model: str = "claude-sonnet-4"
    max_requests_per_session: int = 20


@dataclass(frozen=True)
class InsightsConfig:
    enabled: bool = True
    descriptions: str = "append"  # append | replace | skip


@dataclass(frozen=True)
class DocglowConfig:
    version: int = 1
    title: str = "docglow"
    theme: str = "auto"
    profiling: ProfilingConfig = field(default_factory=ProfilingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    ai: AiConfig = field(default_factory=AiConfig)
    insights: InsightsConfig = field(default_factory=InsightsConfig)
    slim: bool = False
    column_lineage: bool = True
    lineage_layers: LineageLayerConfig = field(default_factory=LineageLayerConfig)

    # Runtime paths (not from config file)
    project_dir: Path = field(default_factory=lambda: Path("."))
    target_dir: Path | None = None
    output_dir: Path | None = None


def load_config(project_dir: Path) -> DocglowConfig:
    """Load configuration from docglow.yml in the project directory.

    Falls back to default config if no file is found.
    """
    for name in ("docglow.yml", "docglow.yaml"):
        config_path = project_dir / name
        if config_path.exists():
            logger.info("Loading config from %s", config_path)
            return _parse_config_file(config_path)

    return DocglowConfig()


def _parse_config_file(path: Path) -> DocglowConfig:
    """Parse a docglow.yml config file into a DocglowConfig."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        logger.warning("Invalid config file %s — using defaults", path)
        return DocglowConfig()

    return _build_config_from_dict(raw)


def _build_naming_rules(raw: dict[str, str]) -> NamingRules:
    """Build NamingRules from a YAML dict, accepting arbitrary layer names.

    Backwards compatibility: ``marts_fact`` and ``marts_dimension`` keys are
    merged into a single ``marts`` layer with multiple patterns.
    """
    # Collect per-layer patterns, preserving insertion order
    layers: dict[str, list[str]] = {}

    # Handle backwards-compat: marts_fact / marts_dimension → marts
    marts_patterns: list[str] = []
    for compat_key in ("marts_fact", "marts_dimension"):
        if compat_key in raw:
            pattern = raw[compat_key]
            try:
                re.compile(pattern)
                marts_patterns.append(pattern)
            except re.error:
                logger.warning(
                    "Invalid regex %r for naming_rules.%s — skipping",
                    pattern,
                    compat_key,
                )
    if marts_patterns:
        layers["marts"] = marts_patterns

    # Process all other keys (skip the compat keys already handled)
    compat_keys = {"marts_fact", "marts_dimension"}
    for k, v in raw.items():
        if k in compat_keys:
            continue
        try:
            re.compile(v)
        except re.error:
            logger.warning(
                "Invalid regex %r for naming_rules.%s — skipping",
                v,
                k,
            )
            continue
        if k in layers:
            layers[k].append(v)
        else:
            layers[k] = [v]

    if not layers:
        return NamingRules()

    return NamingRules(rules=tuple((name, tuple(patterns)) for name, patterns in layers.items()))


def _build_config_from_dict(raw: dict[str, Any]) -> DocglowConfig:
    """Build a DocglowConfig from a parsed YAML dict."""
    health_raw = raw.get("health", {})
    profiling_raw = raw.get("profiling", {})
    ai_raw = raw.get("ai", {})
    lineage_raw = raw.get("lineage_layers", {})

    weights = (
        HealthWeights(
            **{
                k: v
                for k, v in health_raw.get("weights", {}).items()
                if k in HealthWeights.__dataclass_fields__
            }
        )
        if health_raw.get("weights")
        else HealthWeights()
    )

    naming_rules = (
        _build_naming_rules(health_raw.get("naming_rules", {}))
        if health_raw.get("naming_rules")
        else NamingRules()
    )

    complexity = (
        ComplexityThresholds(
            **{
                k: v
                for k, v in health_raw.get("complexity", {}).items()
                if k in ComplexityThresholds.__dataclass_fields__
            }
        )
        if health_raw.get("complexity")
        else ComplexityThresholds()
    )

    profiling = (
        ProfilingConfig(
            enabled=profiling_raw.get("enabled", False),
            sample_size=profiling_raw.get("sample_size", 10000),
            cache=profiling_raw.get("cache", True),
            exclude_schemas=tuple(profiling_raw.get("exclude_schemas", ())),
            top_values_threshold=profiling_raw.get("top_values_threshold", 50),
        )
        if profiling_raw
        else ProfilingConfig()
    )

    ai = (
        AiConfig(
            enabled=ai_raw.get("enabled", False),
            model=ai_raw.get("model", "claude-sonnet-4"),
            max_requests_per_session=ai_raw.get("max_requests_per_session", 20),
        )
        if ai_raw
        else AiConfig()
    )

    lineage_layers = parse_layer_config(lineage_raw) if lineage_raw else LineageLayerConfig()

    insights_raw = raw.get("insights", {})
    insights = (
        InsightsConfig(
            enabled=insights_raw.get("enabled", True),
            descriptions=insights_raw.get("descriptions", "append"),
        )
        if insights_raw
        else InsightsConfig()
    )

    return DocglowConfig(
        version=raw.get("version", 1),
        title=raw.get("title", "docglow"),
        theme=raw.get("theme", "auto"),
        slim=raw.get("slim", False),
        column_lineage=raw.get("column_lineage", True),
        profiling=profiling,
        health=HealthConfig(weights=weights, naming_rules=naming_rules, complexity=complexity),
        ai=ai,
        insights=insights,
        lineage_layers=lineage_layers,
    )
