"""Parse dbt manifest.json artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ManifestMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    dbt_schema_version: str = ""
    dbt_version: str = ""
    generated_at: str = ""
    project_name: str | None = None
    project_id: str | None = None
    adapter_type: str | None = None


class ManifestColumnInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    data_type: str | None = None
    meta: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    quote: bool | None = None
    constraints: list[object] = Field(default_factory=list)


class DependsOn(BaseModel):
    macros: list[str] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)


class TestMetadata(BaseModel):
    name: str = ""
    kwargs: dict[str, object] = Field(default_factory=dict)
    namespace: str | None = None


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    materialized: str | None = None
    schema_: str | None = Field(None, alias="schema")
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True


class ManifestNode(BaseModel):
    """A node in the dbt manifest (model, test, seed, snapshot, etc.)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    unique_id: str
    name: str
    resource_type: str
    package_name: str = ""
    path: str = ""
    original_file_path: str = ""
    database: str | None = None
    schema_: str | None = Field(None, alias="schema")
    description: str = ""
    columns: dict[str, ManifestColumnInfo] = Field(default_factory=dict)
    meta: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    config: NodeConfig = Field(default_factory=NodeConfig)
    depends_on: DependsOn = Field(default_factory=DependsOn)
    raw_code: str = Field("", alias="raw_code")
    compiled_code: str | None = Field(None, alias="compiled_code")
    relation_name: str | None = None

    # Test-specific fields
    test_metadata: TestMetadata | None = None
    column_name: str | None = None

    # Refs and sources used
    refs: list[object] = Field(default_factory=list)
    sources: list[object] = Field(default_factory=list)


class FreshnessRule(BaseModel):
    count: int | None = None
    period: str | None = None


class FreshnessConfig(BaseModel):
    warn_after: FreshnessRule = Field(default_factory=FreshnessRule)
    error_after: FreshnessRule = Field(default_factory=FreshnessRule)
    filter: str | None = None


class ManifestSource(BaseModel):
    """A source definition in the dbt manifest."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    unique_id: str
    name: str
    source_name: str = ""
    source_description: str = ""
    resource_type: str = "source"
    package_name: str = ""
    path: str = ""
    original_file_path: str = ""
    database: str | None = None
    schema_: str | None = Field(None, alias="schema")
    description: str = ""
    columns: dict[str, ManifestColumnInfo] = Field(default_factory=dict)
    meta: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    loader: str = ""
    identifier: str | None = None
    loaded_at_field: str | None = None
    freshness: FreshnessConfig | None = Field(default_factory=FreshnessConfig)
    relation_name: str | None = None


class ManifestExposure(BaseModel):
    """An exposure in the dbt manifest."""

    model_config = ConfigDict(extra="allow")

    unique_id: str
    name: str
    resource_type: str = "exposure"
    type: str = ""
    description: str = ""
    depends_on: DependsOn = Field(default_factory=DependsOn)
    owner: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)


class ManifestMetric(BaseModel):
    """A metric in the dbt manifest."""

    model_config = ConfigDict(extra="allow")

    unique_id: str
    name: str
    resource_type: str = "metric"
    description: str = ""
    label: str = ""
    type: str = ""
    depends_on: DependsOn = Field(default_factory=DependsOn)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)


class Manifest(BaseModel):
    """Parsed dbt manifest.json."""

    model_config = ConfigDict(extra="allow")

    metadata: ManifestMetadata = Field(default_factory=ManifestMetadata)
    nodes: dict[str, ManifestNode] = Field(default_factory=dict)
    sources: dict[str, ManifestSource] = Field(default_factory=dict)
    exposures: dict[str, ManifestExposure] = Field(default_factory=dict)
    metrics: dict[str, ManifestMetric] = Field(default_factory=dict)
    parent_map: dict[str, list[str]] = Field(default_factory=dict)
    child_map: dict[str, list[str]] = Field(default_factory=dict)
