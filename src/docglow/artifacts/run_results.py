"""Parse dbt run_results.json artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunResultsMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    dbt_schema_version: str = ""
    dbt_version: str = ""
    generated_at: str = ""


class TimingEntry(BaseModel):
    name: str = ""
    started_at: str = ""
    completed_at: str = ""


class RunResult(BaseModel):
    """A single result from a dbt run/test/build."""

    model_config = ConfigDict(extra="allow")

    unique_id: str
    status: str = ""
    timing: list[TimingEntry] = Field(default_factory=list)
    thread_id: str = ""
    execution_time: float = 0.0
    adapter_response: dict[str, object] = Field(default_factory=dict)
    message: str | None = None
    failures: int | None = None
    compiled_code: str | None = None


class RunResults(BaseModel):
    """Parsed dbt run_results.json."""

    model_config = ConfigDict(extra="allow")

    metadata: RunResultsMetadata = Field(default_factory=RunResultsMetadata)
    results: list[RunResult] = Field(default_factory=list)
    elapsed_time: float = 0.0
