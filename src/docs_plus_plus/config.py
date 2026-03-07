"""Configuration management for docs-plus-plus."""

from dataclasses import dataclass, field
from pathlib import Path


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
    model: str = "claude-sonnet-4-20250514"
    max_requests_per_session: int = 20


@dataclass(frozen=True)
class DatumConfig:
    version: int = 1
    title: str = "docs-plus-plus"
    theme: str = "auto"
    profiling: ProfilingConfig = field(default_factory=ProfilingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    ai: AiConfig = field(default_factory=AiConfig)

    # Runtime paths (not from config file)
    project_dir: Path = field(default_factory=lambda: Path("."))
    target_dir: Path | None = None
    output_dir: Path | None = None
