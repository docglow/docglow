# Sequence: star expansion in column lineage

**Last updated:** 2026-09-10
**Scope:** The projection-expansion path inside `parse_column_lineage`, before and after DOC-317.
This is the flow that decides which output column names get traced.

## Diagram — current behaviour (the defect)

```mermaid
sequenceDiagram
    participant AN as analyzer.py
    participant PP as parse_column_lineage
    participant EX as _extract_output_columns
    participant CTE as _resolve_star_from_cte
    participant LG as sqlglot lineage()

    AN->>PP: compiled_sql, flat schema, known_columns
    PP->>PP: has_star = any(isinstance(e, exp.Star))

    Note over PP: `renamed.*` is Column(this=Star()),<br/>not Star — so has_star is False

    PP->>EX: select.expressions
    EX-->>PP: ['sk', '*']

    Note over EX: Column branch appends<br/>literal '*' as a column name

    PP->>PP: has_star False, so BOTH the<br/>known_columns branch and<br/>_resolve_star_from_cte are skipped
    PP--xCTE: never called

    loop for each of ['sk', '*']
        PP->>LG: lineage(column, sql, schema)
        LG-->>PP: 'sk' traces / '*' returns nothing
    end

    PP-->>AN: {'sk': deps}

    Note over AN: every real column lost.<br/>`a.*, b.*` yields ['*','*'] and returns {}
```

## Diagram — target behaviour (Approach A)

```mermaid
sequenceDiagram
    participant AN as analyzer.py
    participant PP as parse_column_lineage
    participant Q as sqlglot qualify()
    participant EX as _extract_output_columns
    participant LG as sqlglot lineage()

    AN->>PP: compiled_sql, nested schema, known_columns

    PP->>Q: qualify(tree, schema=nested, infer_schema=True)
    alt every star source resolvable
        Q-->>PP: stars expanded to explicit columns
        Note over Q: covers `renamed.*`, `a.*, b.*`,<br/>EXCLUDE, nested CTEs, UNION, subqueries
    else a source is absent from the schema map
        Q-->>PP: star left in place, no error raised
        Note over Q: qualify() never raises here —<br/>it degrades silently
    end

    PP->>EX: qualified select.expressions
    EX-->>PP: explicit column names only

    Note over EX: star-shape guard drops any<br/>surviving '*' instead of emitting it

    alt unexpanded star remains AND known_columns present
        PP->>PP: fall back to catalog known_columns
        Note over PP: retained on purpose —<br/>`SELECT * FROM raw.src` with the<br/>source missing from schema
    end

    loop for each real output column
        PP->>LG: lineage(column, sql, nested schema)
        LG-->>PP: ColumnDependency list
    end

    PP-->>AN: full lineage for every column
```

## Legend

- `--x` marks a call that is never reached in the current flow — `_resolve_star_from_cte` is dead
  for every qualified-star input, which is why the CTE resolver never masked the bug.
- The `alt` blocks in the target flow are the two verified degradation paths. Both matter: the
  first is why the `'*'` guard survives the rework, the second is why the `known_columns` fallback
  is not deleted.
- `_resolve_star_from_cte` is removed in the target flow. `qualify()` subsumes it and handles
  cases it never could — the resolver matched a single CTE by name against the first `FROM` table
  only.

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2026-09-10 | Initial generation | DOC-317: document the defective and target star-expansion paths |
