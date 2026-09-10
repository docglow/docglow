# Coherence Mapping: DOC-317 qualified star expansion

**Date:** 2026-09-10  
**Tier:** M  
**Plan stem:** `doc-317-handle-qualified-star-expansion-in-column-`  
**Result:** All rows covered. Zero gap, zero fail.

## Row classes

- **outcome** - omitted. Chat/CLI-origin idea; no intake outcomes were staged and `.docs/intake/` does not exist. Not required, not a gap.
- **fr** - omitted. Technical track confirmed in `.docs/track/`; there is no PRD and no `FR-N` ids exist to cite.
- **adr** - present. One non-deleted `.docs/decisions/adr-*.md` in the change set.
- **story** - present. Stories 1 through 6.
- **task** - present. Tasks 1 through 15.
- **criterion** - present. 40 criteria (21 happy, 19 negative).

## Mapping

| Row class | Cited id(s) | Counterpart id(s) | Verdict | Notes |
|---|---|---|---|---|
| adr | adr-2026-09-10-nested-schema-mapping-for-star-expansion | story-1, story-2, story-3, story-4, story-5, story-6 | covered | Decision 1 (nested database-schema-table) implemented by story-4 happy paths 1-2. Decision 2 (alternate keys removed) by story-4 happy path 1 and task-2. Decision 3 (omit nodes missing database or schema) by story-4 negative paths 1-3. Decision 4 (retain known_columns fallback) by story-1 negative path 2 and story-4 negative path 4. The improves-existing-tracing consequence is implemented by story-5 happy path 1. Confirmed against the ADR file text; no story contradicts a decision. |
| story | story-1 | task-7, task-8, task-9 | covered | Qualified single-source star. All 4 happy and 4 negative criteria carry a task. |
| story | story-2 | task-10, task-11, task-12 | covered | Multi-star joins including the duplicate-name decision. All 3 happy and 4 negative criteria carry a task. |
| story | story-3 | task-13 | covered | Qualified-star EXCLUDE. All 2 happy and 3 negative criteria carry a task. |
| story | story-4 | task-1, task-2, task-3, task-4, task-5, task-6 | covered | Nested mapping and the uniform-depth guard. All 3 happy and 5 negative criteria carry a task. |
| story | story-5 | task-6, task-15 | covered | Lineage quality and benchmark cost. All 4 happy and 3 negative criteria carry a task. |
| story | story-6 | task-7, task-15 | covered | Literal-star guard end to end. All 2 happy and 3 negative criteria carry a task. |
| task | task-1 | story-4 | covered | Typed infrastructure supporting story-4 happy path 1. |
| task | task-2 | story-4 | covered | Serves story-4 happy paths 1 and 2. |
| task | task-3 | story-4 | covered | Serves story-4 negative paths 1, 2 and 3 (High-impact risk). |
| task | task-4 | story-4 | covered | Serves story-4 negative path 5. |
| task | task-5 | story-4 | covered | Refactor: type annotations supporting story-4 typed mapping. Explicitly excludes table_resolver.py, whose identical signature is unrelated state. |
| task | task-6 | story-4, story-5 | covered | Serves story-4 Done-When 4 and story-5 negative path 2. |
| task | task-7 | story-6, story-1 | covered | Serves story-6 negative paths 1-2 and story-1 negative path 1. |
| task | task-8 | story-1 | covered | Serves story-1 happy paths 1-3. |
| task | task-9 | story-1, story-4 | covered | Serves story-1 happy path 4 and negative paths 2-4, plus story-4 negative path 4. |
| task | task-10 | story-2 | covered | Serves story-2 happy paths 1-3. |
| task | task-11 | story-2 | covered | Serves story-2 negative path 1 - the operator-confirmed dedupe-first-wins decision. |
| task | task-12 | story-2, story-5, story-6 | covered | Serves story-2 negative paths 2-4, story-5 negative path 1, story-6 negative path 2. |
| task | task-13 | story-3 | covered | Serves all of story-3. |
| task | task-14 | story-1, story-5 | covered | Refactor: removes the hand-rolled CTE star resolver. Surviving observable behaviour is star expansion via qualify(), asserted by story-1 and the pre-existing CTE tests. |
| task | task-15 | story-5, story-6, story-4 | covered | Serves story-5 happy paths 2-4 and negative path 3, story-6 happy path 2 and negative path 3, story-4 happy path 3. |

| criterion | Story 1 happy: Given the SQL `WITH renamed AS (SELECT id, company FROM raw.src) SELECT md5(company) AS sk, renamed.* FROM renamed` and a nested schema containing `raw.src`, when `parse_column_lineage` runs, then the result contains keys `sk`, `id`, and `company`. | task-8 | covered | "returns keys `{sk, id, company}`" | diff-local |
| criterion | Story 1 happy: Given that same SQL, when `parse_column_lineage` runs, then `id` maps to a dependency on source table `raw.src` column `id`, and `company` maps to `raw.src` column `company`. | task-8 | covered | "`id` maps to `(raw.src, id)` and `company` maps to `(raw.src, company)`" | diff-local |
| criterion | Story 1 happy: Given that same SQL, when `parse_column_lineage` runs, then `sk` still maps to `raw.src` column `company` with transformation `derived`, unchanged from current behaviour. | task-8 | covered | "`sk` still maps to `(raw.src, company)` with transformation `derived`" | diff-local |
| criterion | Story 1 happy: Given a qualified star written against a table rather than a CTE (`SELECT a.* FROM raw.a AS a`), when `parse_column_lineage` runs, then every column of `raw.a` appears in the result. | task-9 | covered | "`SELECT a.* FROM raw.a AS a` returns all of `raw.a`'s columns" | diff-local |
| criterion | Story 1 negative: Given the SQL `SELECT renamed.* FROM renamed` where `renamed` resolves to no CTE and no schema entry, when `parse_column_lineage` runs, then the returned dict contains no key equal to the literal string `*`, and the call returns without raising. | task-7 | covered | "returns a dict without a `"*"` key" | diff-local |
| criterion | Story 1 negative: Given a qualified star whose source table is absent from the schema mapping but whose columns are supplied via `known_columns`, when `parse_column_lineage` runs, then the catalog fallback supplies the output column names and lineage is attempted for each. | task-9 | covered | "A star whose table is absent from the mapping falls back to `known_columns`" | diff-local |
| criterion | Story 1 negative: Given SQL that SQLGlot cannot parse at all, when `parse_column_lineage` runs, then it returns an empty dict and does not raise. | task-9 | covered | "Unparseable SQL returns `{}` and raises nothing" | diff-local |
| criterion | Story 1 negative: Given a qualified star against a source whose schema entry exists but lists zero columns, when `parse_column_lineage` runs, then the result contains no literal `*` key and the call returns without raising. | task-9 | covered | "A zero-column source yields a result with no `"*"` key and does not raise" | diff-local |
| criterion | Story 2 happy: Given the SQL `SELECT a.*, b.* FROM raw.a AS a JOIN raw.b AS b ON a.id = b.id` where `raw.a` has columns `id, x` and `raw.b` has columns `id, y`, when `parse_column_lineage` runs, then the result contains keys `id`, `x`, and `y`. | task-10 | covered | "The case-2 SQL returns keys `{id, x, y}`" | diff-local |
| criterion | Story 2 happy: Given that same SQL, when `parse_column_lineage` runs, then `x` maps to a dependency on `raw.a` column `x`, and `y` maps to `raw.b` column `y`. | task-10 | covered | "`x` maps to `(raw.a, x)` and `y` maps to `(raw.b, y)`" | diff-local |
| criterion | Story 2 happy: Given a three-way join projecting three qualified stars, when `parse_column_lineage` runs, then columns from all three sources appear in the result. | task-10 | covered | "A three-way join reports columns from all three sources" | diff-local |
| criterion | Story 2 negative: Given the SQL above where both `raw.a` and `raw.b` carry a column named `id`, when `parse_column_lineage` runs, then `id` appears exactly once in the result, resolves to `raw.a` (the first projected source), and a debug-level log records that a duplicate output column name was collapsed. | task-11 | covered | "`id` appears exactly once in the result and resolves to `raw.a`" | diff-local |
| criterion | Story 2 negative: Given a join where one side is present in the schema mapping and the other is absent, when `parse_column_lineage` runs, then columns from the resolvable side are still reported and the call returns without raising. | task-12 | covered | "A half-resolvable join returns the resolvable side's columns and does not raise" | diff-local |
| criterion | Story 2 negative: Given a join where neither side is present in the schema mapping and no `known_columns` are supplied, when `parse_column_lineage` runs, then the result contains no literal `*` key and the call returns an empty dict rather than raising. | task-12 | covered | "A fully unresolvable join returns `{}` containing no `"*"` key" | diff-local |
| criterion | Story 2 negative: Given a join whose stars expand to more columns than the per-column trace timeout allows, when `parse_column_lineage` runs, then columns that timed out are omitted and the successfully traced columns are still returned. | task-12 | covered | "A per-column timeout omits only that column" | diff-local |
| criterion | Story 3 happy: Given the SQL `SELECT a.* EXCLUDE (x) FROM raw.a AS a` where `raw.a` has columns `id, x`, when `parse_column_lineage` runs, then the result contains key `id` and does not contain key `x`. | task-13 | covered | "`x` is absent and `id` present for qualified-star EXCLUDE" | diff-local |
| criterion | Story 3 happy: Given a bare `SELECT * EXCLUDE (x) FROM raw.a`, when `parse_column_lineage` runs, then `x` is likewise absent, preserving today's behaviour for the unqualified form. | task-13 | covered | "Bare-star EXCLUDE behaviour is asserted unchanged" | diff-local |
| criterion | Story 3 negative: Given `SELECT a.* EXCLUDE (nonexistent) FROM raw.a AS a`, when `parse_column_lineage` runs, then all real columns of `raw.a` are reported and the call returns without raising. | task-13 | covered | "`EXCLUDE (nonexistent)` returns all real columns" | diff-local |
| criterion | Story 3 negative: Given `EXCLUDE` used against a dialect that does not support it, when parsing fails, then `parse_column_lineage` returns an empty dict and does not raise. | task-13 | covered | "an unsupported dialect returns `{}`" | diff-local |
| criterion | Story 3 negative: Given `SELECT a.* EXCLUDE (id, x) FROM raw.a AS a` excluding every column, when `parse_column_lineage` runs, then the result is empty and contains no literal `*` key. | task-13 | covered | "Excluding every column yields an empty result with no `"*"` key" | diff-local |
| criterion | Story 4 happy: Given models and sources carrying `database`, `schema`, and `name`, when `build_schema_mapping` runs, then the returned mapping is nested `database → schema → table → column`, and `raw.a`'s columns are reachable at that path. | task-2 | covered | "`build_schema_mapping` returns a four-level nested dict" | diff-local |
| criterion | Story 4 happy: Given the returned mapping, when it is passed to SQLGlot's `MappingSchema`, then the reported nesting depth is 3 and no error is raised. | task-2 | covered | "`MappingSchema(build_schema_mapping(models, sources)).depth()` equals 3" | diff-local |
| criterion | Story 4 happy: Given a mapping built from the jaffle-shop example manifest and catalog, when column lineage runs end to end, then every model that traced successfully before this change still traces successfully. | task-15 | covered | "Traced-column counts for both example projects are recorded and neither decreased" | diff-local |
| criterion | Story 4 negative: Given a node missing `database`, when `build_schema_mapping` runs, then that node is omitted from the mapping entirely, every other node is still present, and the mapping remains uniform depth 3. | task-3 | covered | "A node missing `database` is absent from the mapping; siblings are present" | diff-local |
| criterion | Story 4 negative: Given a node missing `schema`, when `build_schema_mapping` runs, then that node is omitted and the mapping remains uniform depth 3. | task-3 | covered | "A node missing `schema` is absent from the mapping; siblings are present" | diff-local |
| criterion | Story 4 negative: Given a mapping containing at least one omitted node, when the mapping is handed to `MappingSchema`, then no `SchemaError` about mismatched nesting level is raised. | task-3 | covered | "Constructing `MappingSchema` over a mapping built from such input raises nothing" | diff-local |
| criterion | Story 4 negative: Given a node omitted from the mapping whose columns are known from the catalog, when `parse_column_lineage` runs for that model, then the `known_columns` fallback supplies the output columns and lineage is still attempted. | task-9 | covered | "A star whose table is absent from the mapping falls back to `known_columns`" | diff-local |
| criterion | Story 4 negative: Given two tables sharing a name in different schemas, when `build_schema_mapping` runs, then both are present at their distinct paths and neither overwrites the other. | task-4 | covered | "Both `orders` entries are retrievable at their distinct `database.schema` paths" | diff-local |
| criterion | Story 5 happy: Given `WITH r AS (SELECT id FROM raw.src) SELECT r.id AS id FROM r` and a nested schema, when `parse_column_lineage` runs, then `id` resolves to source table `raw.src` — the correct leaf attribution, rather than the bare `id` the flat mapping produced. | task-15 | covered | "A passing test asserts `id` resolves to source table `raw.src` for the CTE case" | diff-local |
| criterion | Story 5 happy: Given the jaffle-shop example project, when column lineage runs end to end, then the count of successfully traced columns is greater than or equal to the count before this change. | task-15 | covered | "Traced-column counts for both example projects are recorded and neither decreased" | diff-local |
| criterion | Story 5 happy: Given the flowstate example project, when column lineage runs end to end, then the count of successfully traced columns is greater than or equal to the count before this change. | task-15 | covered | "Traced-column counts for both example projects are recorded and neither decreased" | diff-local |
| criterion | Story 5 happy: Given the column-lineage benchmark in `scripts/`, when it runs against the flowstate example on this change, then wall-clock time is within 10% of the pre-change baseline. | task-15 | covered | "within 10% of the pre-change baseline" | diff-local |
| criterion | Story 5 negative: Given a model whose source is absent from the schema mapping and which has no `known_columns`, when `parse_column_lineage` runs, then it returns an empty dict without raising, exactly as before. | task-12 | covered | "A fully unresolvable join returns `{}` containing no `"*"` key" | diff-local |
| criterion | Story 5 negative: Given the parallel `ProcessPoolExecutor` path, when the nested mapping is pickled to workers, then workers produce the same lineage as the serial path for the same model. | task-6 | covered | "A test asserts serial and parallel lineage are equal for the same model" | diff-local |
| criterion | Story 5 negative: Given a benchmark run showing a regression worse than 10%, when the result is reviewed, then the change is not merged until the regression is explained or removed. | task-15 | covered | "within 10% of the pre-change baseline" | diff-local |
| criterion | Story 6 happy: Given any SQL in which every star expands successfully, when `parse_column_lineage` runs, then no result key equals `*`. | task-7 | covered | "returns a dict without a `"*"` key" | diff-local |
| criterion | Story 6 happy: Given the jaffle-shop and flowstate example projects, when column lineage runs end to end, then no model's lineage contains a column named `*`. | task-15 | covered | "No lineage entry across either example project is keyed `"*"`" | diff-local |
| criterion | Story 6 negative: Given SQL whose star cannot be expanded because `qualify` left it in place, when `parse_column_lineage` runs, then the unexpanded star is dropped rather than emitted as a column named `*`. | task-7 | covered | "`_extract_output_columns` on `SELECT a.*, b.* FROM ...` returns `[]`, not `["*", "*"]`" | diff-local |
| criterion | Story 6 negative: Given SQL with a qualified star that cannot be expanded and no `known_columns`, when `parse_column_lineage` runs, then it returns an empty dict rather than a dict keyed by `*`. | task-12 | covered | "A fully unresolvable join returns `{}` containing no `"*"` key" | diff-local |
| criterion | Story 6 negative: Given a model whose lineage was previously written to the on-disk cache with a `*` key by an older docglow version, when lineage is recomputed after a version change, then the regenerated entry contains no `*` key. | task-15 | covered | "A test proves a stale cache entry carrying a `"*"` key is regenerated without it" | diff-local |

## Consistency pass (section 4d)

Cross-layer pairs were checked in both directions. Same-layer story-vs-story pairs are `/conflict-check`'s sweep and are not re-reported here. No contradiction or oscillation was found, so no `fail` row was recorded and no artifact required amendment for a contradiction.

- **adr decision 3 (omit malformed nodes) vs story-5 count floor.** Forward: omitting a malformed node could in principle lower the traced count story-5 guards. Reverse: holding the count floor does not require inserting a malformed node, because the known_columns fallback compensates. No oscillation - verified that 0 of 525 nodes and sources across jaffle-shop (47) and flowstate (478) lack `database` or `schema`, so the omission rule cannot fire on either project story-5 measures.
- **adr decision 2 (alternate keys removed) vs story-4 happy path 1.** Mutually required: the nested shape cannot coexist with the flat keys, because MappingSchema enforces a single depth.
- **adr decision 4 (retain fallback) vs task-14 (delete the CTE star resolver).** Consistent: the retained fallback is known_columns, not the CTE resolver; the two are separate paths.
- **story-3 EXCLUDE vs story-5 count floor.** No contradiction: a qualified-star EXCLUDE model traces to nothing today, so any post-change result is an increase, and bare-star EXCLUDE is asserted unchanged by story-3 happy path 2.
- **story-6 (no literal star column) vs story-5 count floor.** No contradiction: parse_column_lineage records a key only when the trace returns dependencies, and a literal star resolves to none, so no such key exists today to remove.

## Coverage corrections applied during this pass

Two criteria had zero covering task when this artifact was first derived. Both were closed by amending the plan during DECIDE, before BUILD:

- **S1N3** (unparseable SQL returns an empty dict without raising) - no task covered it and no existing test asserted it. Added to task-9 steps and Done-When.
- **S6N3** (a stale cache entry carrying a star key regenerates without it) - no task covered it. Added to task-15 steps and Done-When, with `tests/lineage/test_analyzer.py` added to that task's Files.

Both are recorded as covered above because the plan now covers them; the corrections are visible in this spec's own commit history.
