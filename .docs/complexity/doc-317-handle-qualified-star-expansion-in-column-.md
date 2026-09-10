# Complexity: DOC-317 qualified star expansion in column lineage

Tier: M

## Rationale

Medium, not Small, because the fix cannot stay inside the star guard. The operator-confirmed broad
scope requires reshaping the schema contract that feeds both `qualify()` and the existing
`lineage()` calls, and that contract crosses a module boundary, a process boundary, and six tests.

Medium, not Large, because it is confined to one module's public surface, adds no dependency, no
migration, no schema/API change, and no frontend work.

## Sizing signals

| Signal | Finding |
|---|---|
| Modules touched | 2 (`lineage/column_parser.py`, `lineage/analyzer.py`) |
| New dependencies | 0 — `sqlglot.optimizer.qualify` already installed (29.0.1) |
| Public contract change | Yes — `build_schema_mapping` return shape flips flat-dotted to nested |
| Existing tests asserting old shape | 6 call sites across 3 test files |
| Process boundary | Schema is pickled to ProcessPoolExecutor workers (`_worker_schema`) |
| Verified regression risk | Yes — see constraints below |
| Rough effort | ~half day |

## Load-bearing constraints (verified against sqlglot 29.0.1)

1. **`MappingSchema` requires consistent nesting depth.** A mapping mixing depth 1 and depth 2
   raises `SchemaError`. `build_schema_mapping` currently indexes every table under three key
   formats at once (bare `name`, `schema.name`, `database.schema.name`). That deliberate
   flexibility cannot survive the move to nested form — the rework must choose one canonical
   depth and make table references resolve against it. This is the single largest design
   decision in the change and is why architecture review is warranted.

2. **The flat shape is itself degrading existing lineage.** With flat keys, tracing
   `WITH r AS (SELECT id FROM raw.src) SELECT r.id FROM r` resolves the leaf to `id`; with nested
   it correctly resolves to `src.id`. Bare `SELECT * FROM raw.src` expands only under the nested
   shape. The reshape therefore improves tracing that is in no way part of the reported bug —
   which also means it can move existing test expectations.

3. **`known_columns` fallback must be retained.** `SELECT * FROM raw.src` where the source is
   absent from the schema map stays unexpanded under `qualify()`. Dropping the catalog path
   regresses projects with an incomplete catalog.

4. **`qualify()` never raises on an unknown table** — it silently leaves the star in place. The
   guard preventing a literal `'*'` from becoming an output column name is still required after
   qualify() lands.

5. **Duplicate output names.** `SELECT a.*, b.* FROM a JOIN b` where both sources carry `id`
   yields two `id` projections. The lineage result is a dict keyed by column name, so one
   silently clobbers the other. Needs an explicit decision, not a default.

## Tier-required artifacts

Per Medium: architecture diagram, lightweight architecture review, conflict-check, and
coherence-check are all in scope. No PRD — track is technical.
