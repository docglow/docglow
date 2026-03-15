# Plan: Column-Level Lineage via SQLGlot

## Overview

Add column-level lineage tracking to docglow by using SQLGlot's built-in `sqlglot.lineage` module to parse compiled SQL and trace which source columns feed into which output columns.

## Data Flow

```
compiled_sql (from manifest) → SQLGlot lineage() → column dependency graph → JSON payload → frontend UI
```

## Payload Shape

```json
{
  "column_lineage": {
    "model.project.dim_customers": {
      "customer_id": [
        {
          "source_model": "source.project.raw.customers",
          "source_column": "id",
          "transformation": "direct"
        }
      ],
      "total_orders": [
        {
          "source_model": "model.project.stg_orders",
          "source_column": "customer_id",
          "transformation": "aggregated"
        }
      ]
    }
  }
}
```

## TypeScript Types

```typescript
interface ColumnLineageDependency {
  source_model: string
  source_column: string
  transformation: 'direct' | 'derived' | 'aggregated'
}

type ColumnLineageData = Record<string, Record<string, ColumnLineageDependency[]>>
```

## Implementation Phases

### Phase 1: Backend — SQLGlot Parsing Engine

**Step 1.1: Add `sqlglot` optional dependency**
- File: `pyproject.toml`
- Add `column-lineage = ["sqlglot>=26.0"]` to `[project.optional-dependencies]`

**Step 1.2: Create column lineage parser module**
- Files: `src/docglow/lineage/__init__.py`, `src/docglow/lineage/column_parser.py`
- Functions:
  - `parse_column_lineage(compiled_sql, schema, dialect) -> dict[str, list[ColumnDep]]`
  - `detect_dialect(adapter_type) -> str`
  - `build_schema_mapping(models, sources, catalog) -> dict[str, dict[str, str]]`
  - `classify_transformation(expression_ast) -> str`

**Step 1.3: Create table name resolver**
- File: `src/docglow/lineage/table_resolver.py`
- Map SQLGlot table references back to dbt unique_ids using `relation_name` from manifest
- Handle case-insensitive matching (Snowflake uppercases, BigQuery lowercases)

**Step 1.4: Integrate into data builder**
- File: `src/docglow/generator/data.py`
- Add `column_lineage_enabled: bool = False` parameter to `build_docglow_data`
- Wrap parse calls in try/except, log warnings and skip on failure

**Step 1.5: Add CLI flag**
- File: `src/docglow/cli.py`
- Add `--column-lineage` / `--no-column-lineage` flag, default off

### Phase 2: Frontend — Column Table Integration

**Step 2.1**: Extend TypeScript types with `ColumnLineageDependency`
**Step 2.2**: Add accessor methods to project store
**Step 2.3**: Add lineage indicators to ColumnTable component

### Phase 3: Frontend — Lineage Graph Column Highlighting (Deferred)

**Step 3.1**: Column-aware DagNode expansion
**Step 3.2**: Column-level edge tracing in LineageFlow

### Phase 4: Testing

**Step 4.1**: Unit tests for column parser (SQL parsing, dialects, edge cases)
**Step 4.2**: Unit tests for table resolver (exact match, case-insensitive, unresolvable)
**Step 4.3**: Integration test for data builder with mock fixtures

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Jinja in raw SQL | Low | Use `compiled_sql` only (Jinja already resolved) |
| SQLGlot parse failures | Medium | try/except per model, log and skip |
| Table name resolution mismatches | High | Lookup via `relation_name`, fallback to fuzzy `(schema, name)` |
| `SELECT *` expansion | Medium | Use catalog column data; show `*` when missing |
| Performance on 500+ models | Medium | Per-model parsing is parallelizable; cache by SQL hash |
| Payload size | Low | Column lineage is sparse (~50-100KB for 200 models) |

## Dependencies

| Dependency | Version | Type | Size |
|-----------|---------|------|------|
| `sqlglot` | >=26.0 | Optional (`column-lineage` extra) | ~2MB |

SQLGlot is pure Python with zero transitive dependencies.

## Key Files

**Backend:**
- `pyproject.toml` — optional dependency
- `src/docglow/lineage/__init__.py` — new package
- `src/docglow/lineage/column_parser.py` — core parsing
- `src/docglow/lineage/table_resolver.py` — dbt unique_id resolution
- `src/docglow/generator/data.py` — integration point
- `src/docglow/cli.py` — CLI flag

**Frontend:**
- `frontend/src/types/index.ts`
- `frontend/src/stores/projectStore.ts`
- `frontend/src/components/models/ColumnTable.tsx`
- `frontend/src/components/lineage/DagNode.tsx` (Phase 3)
- `frontend/src/components/lineage/LineageFlow.tsx` (Phase 3)

**Tests:**
- `tests/lineage/test_column_parser.py`
- `tests/lineage/test_table_resolver.py`
- `tests/lineage/test_data_column_lineage.py`
