"""Parse dbt catalog.json artifacts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CatalogMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    dbt_schema_version: str = ""
    dbt_version: str = ""
    generated_at: str = ""


class CatalogColumnInfo(BaseModel):
    name: str
    type: str = ""
    index: int = 0
    comment: str | None = None


class CatalogStat(BaseModel):
    id: str
    label: str = ""
    value: object = None
    include: bool = False
    description: str = ""


class CatalogNodeMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str = ""
    schema_: str | None = Field(None, alias="schema")
    name: str = ""
    database: str | None = None
    comment: str | None = None
    owner: str | None = None


class CatalogNode(BaseModel):
    """A node (table/view) in the dbt catalog."""

    unique_id: str
    metadata: CatalogNodeMetadata = Field(default_factory=CatalogNodeMetadata)
    columns: dict[str, CatalogColumnInfo] = Field(default_factory=dict)
    stats: dict[str, CatalogStat] = Field(default_factory=dict)


class Catalog(BaseModel):
    """Parsed dbt catalog.json."""

    metadata: CatalogMetadata = Field(default_factory=CatalogMetadata)
    nodes: dict[str, CatalogNode] = Field(default_factory=dict)
    sources: dict[str, CatalogNode] = Field(default_factory=dict)
    errors: list[str] | None = None
