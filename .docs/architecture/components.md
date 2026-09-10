# Components: Docglow column lineage subsystem

**Last updated:** 2026-09-10
**Scope:** C4 L3 for the `src/docglow/lineage/` container only. Scoped deliberately to the
subsystem DOC-317 changes; docglow is a single-process CLI with no database or message queue, so
system-context, container, and ERD diagrams would be fabricated rather than derived.

## Diagram

```mermaid
graph TD
    subgraph artifacts["artifacts/ — dbt artifact loader"]
        MANIFEST["manifest + catalog<br/>models, sources, columns"]
    end

    subgraph lineage["lineage/ — column lineage subsystem"]
        ANALYZER["analyzer.py<br/>orchestrator"]
        POOL["ProcessPoolExecutor<br/>_worker_schema global"]
        PARSER["column_parser.py<br/>parse_column_lineage"]
        SCHEMAMAP["column_parser.py<br/>build_schema_mapping"]
        RESOLVER["table_resolver.py<br/>SQL refs to dbt unique_ids"]
        MACRO["macro_expander.py<br/>Jinja to SQL"]
    end

    subgraph sqlglot["SQLGlot — external library"]
        QUALIFY["optimizer.qualify<br/>expand_stars"]
        LINEAGE["lineage.lineage<br/>column tracing"]
        SCHEMA["MappingSchema<br/>fixed nesting depth"]
    end

    GEN["generator/ — DocglowData payload"]

    MANIFEST --> ANALYZER
    MANIFEST --> SCHEMAMAP
    ANALYZER --> SCHEMAMAP
    ANALYZER --> MACRO
    ANALYZER --> POOL
    POOL --> PARSER
    SCHEMAMAP -->|nested schema mapping| POOL
    PARSER --> QUALIFY
    PARSER --> LINEAGE
    QUALIFY --> SCHEMA
    LINEAGE --> SCHEMA
    PARSER -->|ColumnDependency list| ANALYZER
    ANALYZER --> RESOLVER
    RESOLVER --> GEN

    style QUALIFY fill:#e8f4d9
    style SCHEMAMAP fill:#e8f4d9
    style PARSER fill:#fdf1d6
```

## Legend

- **Green** — components whose contract DOC-317 changes. `build_schema_mapping` flips its return
  shape from flat-dotted keys to nested `MappingSchema` form; `optimizer.qualify` becomes a new
  call site inside `parse_column_lineage`.
- **Amber** — `parse_column_lineage`, modified but contract-stable: same signature, same
  `dict[str, list[ColumnDependency]]` return.
- **Unstyled** — untouched by this change.
- The `SCHEMAMAP` to `POOL` edge crosses a **process boundary**: the mapping is pickled into
  worker processes and held in the `_worker_schema` module global. Its shape change therefore
  propagates to every worker, not just the parent.
- `MappingSchema` enforces a **single nesting depth** across the whole mapping. This is the
  constraint that makes the reshape a design decision rather than a mechanical edit.

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2026-09-10 | Initial generation, scoped to the lineage subsystem | DOC-317 tier M requires an architecture diagram; no prior diagrams existed |
