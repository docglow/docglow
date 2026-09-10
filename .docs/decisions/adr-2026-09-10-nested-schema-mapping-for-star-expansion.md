# ADR: Canonical three-part nesting for the column-lineage schema mapping

**Date:** 2026-09-10
**Status:** APPROVED
**Feature:** DOC-317 qualified star expansion in column lineage

## Context

`build_schema_mapping` (`src/docglow/lineage/column_parser.py`) produces the table-to-columns
mapping handed to SQLGlot. Today it indexes every table under **three key formats at once** —
bare `name`, `schema.name`, and `database.schema.name` — plus `source_name.name` for sources,
on the theory that flexible matching maximises the chance a SQL table reference resolves.

DOC-317 requires expanding qualified stars (`renamed.*`, `a.* , b.*`). The approved approach
delegates that to `sqlglot.optimizer.qualify.qualify()`, which resolves stars through
`MappingSchema`. This forces a decision that the flat-key design has been deferring.

**`MappingSchema` requires one consistent nesting depth across the entire mapping.** (verified,
98% — sqlglot 29.0.1 raises `SchemaError: Table raw.other must match the schema's nesting level: 1`
on a mapping mixing depth 1 and depth 2.) The current multi-key flat design cannot be expressed as
a `MappingSchema` at all; passing it yields depth-1 behaviour in which three-part SQL references
silently fail to resolve — no exception, stars simply stay unexpanded.

This is a structural decision: it fixes the canonical addressing scheme for every table identity
flowing across the `build_schema_mapping` → analyzer → ProcessPoolExecutor worker → SQLGlot seam.

## Decision

**The schema mapping is nested at a single canonical depth of three: `database → schema → table`.**

1. `build_schema_mapping` returns `{database: {schema: {table: {column: type}}}}`.
2. The bare-`name`, `schema.name`, and `source_name.name` alternate keys are **removed**, not
   translated. They are unreachable for SQL matching (see Evidence).
3. A node missing either `database` or `schema` is **omitted** from the mapping rather than
   inserted at a shorter depth, because a mixed-depth mapping raises and would take down lineage
   for the whole project rather than one model.
4. The `known_columns` catalog fallback in `parse_column_lineage` is **retained**. It is the
   compensating path for any table omitted by rule 3 or absent from the mapping.

## Evidence

Measured across the two bundled example projects' real dbt-compiled SQL:

| Project | 3-part refs (`db.schema.table`) | 2-part refs | 1-part refs (CTE names) |
|---|---|---|---|
| flowstate (432 models) | 489 | 0 | 95 |
| jaffle-shop (13 models) | 17 | 0 | 32 |

- dbt compiles `ref()` and `source()` to the **fully-qualified physical relation**, always
  three-part. (verified, 95%)
- **No two-part reference occurs in either project.** The `schema.name` and `source_name.name`
  keys therefore never match a real SQL table reference — dbt never emits `ecom.raw_customers`
  into compiled SQL, only `jaffle_shop.raw.raw_customers`. Removing them loses no matching
  ability. (verified, 92% — measured on two projects, not proven across all adapters)
- One-part references are **CTE names**, which SQLGlot resolves from the CTE body itself and never
  looks up in the schema. The bare-`name` key is likewise unreachable. (verified, 90%)
- Nesting is not merely a prerequisite for `qualify()` — it **improves existing tracing**. Under
  the flat mapping, `WITH r AS (SELECT id FROM raw.src) SELECT r.id FROM r` resolves its leaf to
  `id`; nested resolves it correctly to `src.id`. Bare `SELECT * FROM raw.src` expands only under
  the nested shape. (verified, 95%)

## Consequences

**Positive**
- `qualify()` can expand qualified stars, multi-star joins, `EXCLUDE`, nested CTE chains, UNION,
  and subqueries — a strict superset of what `_resolve_star_from_cte` handled (single CTE only),
  which is then deleted.
- Leaf table attribution in existing lineage becomes correct, not just star handling.
- The mapping shrinks roughly threefold — one key per table instead of three — which reduces the
  payload pickled to every ProcessPoolExecutor worker.

**Negative / accepted**
- `build_schema_mapping`'s return shape is a breaking change for its callers. Two production call
  sites (`analyzer.py:272`, `analyzer.py:406`) and six test call sites across three test files
  must move together.
- Any table genuinely referenced by a bare or two-part name in a dialect we have not measured
  would stop resolving via the schema and fall to `known_columns`. Accepted: the fallback exists
  precisely for this, and no such reference was observed.
- Column-lineage cache entries are keyed by SQL hash and docglow version, so improved resolution
  will not be masked by stale cache on a version bump. No cache migration required.

## Alternatives rejected

- **Keep flat keys, hand `qualify()` a separately-built nested copy.** Two mappings to keep in
  sync, double the pickled payload, and leaves the verified leaf-attribution defect unfixed.
- **Normalise to depth 1 (bare table name).** Would collide any two tables sharing a name across
  schemas — routine in dbt projects with staging and mart layers.
- **Depth 2 (`schema.table`).** Matches no observed reference and still collides across databases.

## Wiring Surface

No new production surface. `build_schema_mapping` and `parse_column_lineage` keep their names and
call sites; only the mapping's internal shape changes. `qualify()` is called from inside
`parse_column_lineage`, which is already invoked from `analyzer.py:171` and from the worker entry
point that reads `_worker_schema`.
