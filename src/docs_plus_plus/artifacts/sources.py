"""Parse dbt sources.json (source freshness) artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SourcesMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    dbt_schema_version: str = ""
    dbt_version: str = ""
    generated_at: str = ""


class FreshnessCriteria(BaseModel):
    warn_after: dict[str, object] = Field(default_factory=dict)
    error_after: dict[str, object] = Field(default_factory=dict)
    filter: str | None = None


class FreshnessTimingEntry(BaseModel):
    name: str = ""
    started_at: str = ""
    completed_at: str = ""


class SourceFreshnessResult(BaseModel):
    """A single source freshness result."""

    model_config = ConfigDict(extra="allow")

    unique_id: str
    status: str = ""
    max_loaded_at: str = ""
    snapshotted_at: str = ""
    max_loaded_at_time_ago_in_s: float = 0.0
    criteria: FreshnessCriteria = Field(default_factory=FreshnessCriteria)
    adapter_response: dict[str, object] = Field(default_factory=dict)
    timing: list[FreshnessTimingEntry] = Field(default_factory=list)
    thread_id: str = ""
    execution_time: float = 0.0


class SourceFreshness(BaseModel):
    """Parsed dbt sources.json (source freshness results)."""

    model_config = ConfigDict(extra="allow")

    metadata: SourcesMetadata = Field(default_factory=SourcesMetadata)
    results: list[SourceFreshnessResult] = Field(default_factory=list)
    elapsed_time: float = 0.0
