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
    staging: str = r"^stg_"
    intermediate: str = r"^int_"
    marts_fact: str = r"^fct_"
    marts_dimension: str = r"^dim_"


@dataclass(frozen=True)
class ComplexityThresholds:
    high_sql_lines: int = 200
    high_join_count: int = 8
    high_cte_count: int = 10


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
    """Build NamingRules, validating each regex and falling back to defaults."""
    defaults = NamingRules()
    validated: dict[str, str] = {}
    for k, v in raw.items():
        if k not in NamingRules.__dataclass_fields__:
            continue
        try:
            re.compile(v)
            validated[k] = v
        except re.error:
            default_val = getattr(defaults, k)
            logger.warning(
                "Invalid regex %r for naming_rules.%s — falling back to default %r",
                v,
                k,
                default_val,
            )
            validated[k] = default_val
    return NamingRules(**validated)


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
