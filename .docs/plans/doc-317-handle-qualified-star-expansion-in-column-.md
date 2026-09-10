# Implementation Plan: DOC-317 qualified star expansion in column lineage

**Date:** 2026-09-10
**Stories:** .docs/stories/doc-317-handle-qualified-star-expansion-in-column-.md
**Design:** .docs/decisions/adr-2026-09-10-nested-schema-mapping-for-star-expansion.md
**Conflict check:** Clean as of 2026-09-10

## Summary

Reshape the column-lineage schema mapping to SQLGlot's nested depth-3 form, then delegate star
expansion to `sqlglot.optimizer.qualify.qualify()`. 15 tasks covering 6 stories.

## Technical Approach

Two phases, strictly ordered. **The reshape lands first** and is independently valuable — under the
flat mapping, SQLGlot resolves `WITH r AS (SELECT id FROM raw.src) SELECT r.id FROM r` to a bare
leaf `id` rather than `src.id`, so nesting fixes existing leaf attribution before any star work
begins. Only once the mapping is nested can `qualify()` expand stars at all.

**Phase 1 — the mapping (Tasks 1-6, Story 4).** `build_schema_mapping` returns
`{database: {schema: {table: {column: type}}}}`. The bare-`name`, `schema.name`, and
`source_name.name` alternate keys are removed outright: measured across both example projects,
dbt compiles every `ref()`/`source()` to a fully-qualified three-part relation (489 + 17
references), zero two-part references exist, and one-part references are CTE names SQLGlot
resolves from the CTE body without consulting the schema. A node missing `database` or `schema` is
**omitted** rather than inserted at a shorter depth, because `MappingSchema` raises `SchemaError`
on a mixed-depth mapping — one malformed node would otherwise remove lineage project-wide.

**Phase 2 — star expansion (Tasks 7-15, Stories 1, 2, 3, 6).** `parse_column_lineage` runs
`qualify()` before extracting output columns. `_resolve_star_from_cte` is deleted: `qualify()`
subsumes it and additionally handles joins, `EXCLUDE`, nested CTE chains, UNION, and subqueries,
none of which the single-CTE resolver could do. `qualify()` never raises on an unresolvable table —
it silently leaves the star in place — so the literal-`*` guard in `_extract_output_columns` is
required *after* qualify, not instead of it, and the `known_columns` catalog fallback stays.

**Two traps to avoid.**
1. `table_resolver.py:88` and `:102` carry the *identical* type signature
   `dict[str, dict[str, str]]`, but that is the resolver's own `exact`/`lower`/`short` serialization
   state and is semantically unrelated to the schema mapping. **Do not reshape it.** Only the ten
   annotation sites in `analyzer.py` and `column_parser.py` change.
2. The schema crosses a process boundary via `_init_worker` into the `_worker_schema` global and is
   transported through `serialize_shared_state`/`deserialize_shared_state`. The nested form stays
   plain nested dicts of `str`, so it remains JSON-serializable and picklable — verify, don't assume.

**Local test pattern.** Existing lineage tests in `tests/lineage/test_column_parser.py` construct
SQL inline as a string, call `parse_column_lineage` directly, and assert on the returned dict's
keys and `(source_table, source_column)` tuples. New tests should preserve those traits — inline
SQL, direct call, assertions on the returned mapping — rather than introducing fixtures or a
manifest round-trip. Find comparable examples by searching that file for `parse_column_lineage(`.

## Prerequisites

- `sqlglot >= 29.0.1` with the `column-lineage` extra installed (`pip install -e ".[dev,column-lineage]"`). Already a declared dependency; no version bump.
- No migration, no config change, no cache invalidation step — the lineage cache is keyed by SQL hash plus docglow version.

## Tasks

### Task 1: Nested schema type alias
**Story:** Story 4, happy path 1
**Type:** infrastructure

**Steps:**
1. Write failing test asserting `build_schema_mapping` output is subscriptable as `result["jaffle_shop"]["main"]["orders"]["order_id"]`.
2. Verify test fails (RED).
3. Add a module-level type alias `NestedSchema = dict[str, dict[str, dict[str, dict[str, str]]]]` in `column_parser.py`.
4. Verify the alias imports cleanly and `mypy src/docglow` reports no new error.
5. Commit: "refactor(lineage): add nested schema type alias"

**Done when:**
- [ ] `NestedSchema` is defined in `src/docglow/lineage/column_parser.py`.
- [ ] `mypy src/docglow` exits 0.
- [ ] The new test still fails (the alias alone does not change behaviour).

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — add type alias
- `tests/lineage/test_column_parser.py` — add failing nesting test

**Dependencies:** none

---

### Task 2: build_schema_mapping returns nested depth-3
**Story:** Story 4, happy paths 1 and 2
**Type:** happy-path

**Steps:**
1. Keep Task 1's test as the RED case.
2. Rewrite `build_schema_mapping` to emit `{database: {schema: {table: {column: type}}}}`, removing the bare-`name`, `schema.name`, and `source_name.name` `setdefault` calls.
3. Verify test passes (GREEN).
4. Add an assertion that `MappingSchema(result).depth()` equals 3.
5. Commit: "refactor(lineage): nest schema mapping at database.schema.table"

**Done when:**
- [ ] `build_schema_mapping` returns a four-level nested dict.
- [ ] `MappingSchema(build_schema_mapping(models, sources)).depth()` equals 3 in a passing test.
- [ ] No `setdefault` producing a bare-name or two-part key remains in the function.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — rewrite `build_schema_mapping`
- `tests/lineage/test_column_parser.py` — nesting and depth assertions

**Dependencies:** Task 1

---

### Task 3: Omit nodes missing database or schema
**Story:** Story 4, negative paths 1, 2 and 3 (High-impact risk)
**Type:** negative-path

**Steps:**
1. Write failing tests: a node missing `database`, and a node missing `schema`, are each absent from the mapping while sibling nodes remain present.
2. Write a failing test asserting `MappingSchema(result)` does not raise `SchemaError` when such a node was present in the input.
3. Verify tests fail (RED).
4. Add the guard: skip a node when `database` or `schema` is falsy, before inserting.
5. Verify tests pass (GREEN). Commit: "fix(lineage): omit nodes missing database or schema from the mapping"

**Done when:**
- [ ] A node missing `database` is absent from the mapping; siblings are present.
- [ ] A node missing `schema` is absent from the mapping; siblings are present.
- [ ] Constructing `MappingSchema` over a mapping built from such input raises nothing.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — omission guard in `build_schema_mapping`
- `tests/lineage/test_column_parser.py` — three negative-path tests

**Dependencies:** Task 2

---

### Task 4: Same-named tables in different schemas coexist
**Story:** Story 4, negative path 5
**Type:** negative-path

**Steps:**
1. Write failing test: two tables both named `orders`, in schemas `staging` and `marts`, both appear at their distinct paths with their own columns.
2. Verify test fails or passes trivially (RED/confirm).
3. Confirm the nested write path does not overwrite; fix if it does.
4. Verify test passes (GREEN). Commit: "test(lineage): same-named tables in different schemas coexist"

**Done when:**
- [ ] Both `orders` entries are retrievable at their distinct `database.schema` paths.
- [ ] Neither entry's column dict is empty or equal to the other's.

**Files likely touched:**
- `tests/lineage/test_column_parser.py` — collision test
- `src/docglow/lineage/column_parser.py` — only if a fix is needed

**Dependencies:** Task 2

---

### Task 5: Update the ten schema type annotations
**Story:** Story 4, happy path 1 (type correctness)
**Type:** refactor

**Steps:**
1. Change the schema annotations to `NestedSchema` at `analyzer.py` lines 97, 103, 133, 282, 295, 303 and `column_parser.py` lines 53, 189, 517, 523.
2. Leave `table_resolver.py` lines 88 and 102 **unchanged** — that signature is the resolver's own `exact`/`lower`/`short` state, not the schema mapping.
3. Run `mypy src/docglow`.
4. Verify it exits 0. Commit: "refactor(lineage): annotate the nested schema type"

**Done when:**
- [ ] `mypy src/docglow` exits 0.
- [ ] `grep -n "dict\[str, dict\[str, str\]\]" src/docglow/lineage/table_resolver.py` still returns both original lines.
- [ ] No schema-carrying parameter in `analyzer.py` or `column_parser.py` retains the old two-level annotation.

**Files likely touched:**
- `src/docglow/lineage/analyzer.py` — six annotation sites
- `src/docglow/lineage/column_parser.py` — four annotation sites

**Dependencies:** Task 2

---

### Task 6: Migrate the flat-shape test call sites and confirm worker transport
**Story:** Story 4, Done-When 4; Story 5, negative path 2
**Type:** refactor

**Steps:**
1. Update the flat-shape assertions in `tests/lineage/test_column_parser.py` (`schema["public.users"]`, `schema["s.t"]`, `schema["users"]`) to their nested paths.
2. Update the two `build_schema_mapping` call sites in `tests/test_column_lineage_parallel.py` and the assertion in `tests/lineage/test_source_column_lineage.py`.
3. Add a test asserting the serial and parallel paths return identical lineage for one model, proving the nested mapping survives `_init_worker` and `serialize_shared_state`.
4. Run `pytest`. Commit: "test(lineage): migrate schema assertions to the nested shape"

**Done when:**
- [ ] `pytest` passes with zero failures.
- [ ] `grep -rn 'schema\["[a-z_]*\.[a-z_]*"\]' tests/` returns no flat dotted schema subscript.
- [ ] A test asserts serial and parallel lineage are equal for the same model.

**Files likely touched:**
- `tests/lineage/test_column_parser.py` — migrate assertions
- `tests/test_column_lineage_parallel.py` — migrate two call sites, add agreement test
- `tests/lineage/test_source_column_lineage.py` — migrate assertion

**Dependencies:** Task 3, Task 4, Task 5

---

### Task 7: Guard against a literal star becoming a column name
**Story:** Story 6, negative paths 1 and 2; Story 1 negative path 1
**Type:** negative-path

**Steps:**
1. Write failing test: `parse_column_lineage("SELECT renamed.* FROM renamed", schema={})` returns a dict with no key `"*"`.
2. Verify test fails (RED) — today `_extract_output_columns` appends the literal `*`.
3. In `_extract_output_columns`, skip an `exp.Column` whose `.this` is an `exp.Star`, matching the existing bare-`exp.Star` skip.
4. Verify test passes (GREEN). Commit: "fix(lineage): never emit a literal star as an output column name"

**Done when:**
- [ ] `parse_column_lineage` on an unresolvable qualified star returns a dict without a `"*"` key.
- [ ] `_extract_output_columns` on `SELECT a.*, b.* FROM ...` returns `[]`, not `["*", "*"]`.
- [ ] The call returns without raising.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — `_extract_output_columns` guard
- `tests/lineage/test_column_parser.py` — literal-star tests

**Dependencies:** Task 6

---

### Task 8: Expand stars via qualify() before extracting output columns
**Story:** Story 1, happy paths 1-3
**Type:** happy-path

**Steps:**
1. Write failing test: the case-1 SQL `WITH renamed AS (SELECT id, company FROM raw.src) SELECT md5(company) AS sk, renamed.* FROM renamed` returns keys `{sk, id, company}`.
2. Verify test fails (RED).
3. In `parse_column_lineage`, call `qualify(parsed_tree, schema=nested_schema, infer_schema=True)` inside a `try/except` before extracting output columns; on exception fall through to the unqualified tree.
4. Verify test passes (GREEN). Commit: "feat(lineage): expand qualified stars via sqlglot qualify()"

**Done when:**
- [ ] The case-1 SQL returns exactly the keys `{sk, id, company}`.
- [ ] `id` maps to `(raw.src, id)` and `company` maps to `(raw.src, company)`.
- [ ] `sk` still maps to `(raw.src, company)` with transformation `derived`.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — qualify() call in `parse_column_lineage`
- `tests/lineage/test_column_parser.py` — case-1 tests

**Dependencies:** Task 7

---

### Task 9: Qualified star against a plain table
**Story:** Story 1, happy path 4; negative paths 2 and 4
**Type:** happy-path

**Steps:**
1. Write failing tests: `SELECT a.* FROM raw.a AS a` returns every column of `raw.a`; a star whose source is absent from the mapping but present in `known_columns` uses the fallback; a source with zero columns yields no `"*"` key; SQL SQLGlot cannot parse at all returns an empty dict without raising.
2. Verify tests fail (RED).
3. Confirm the Task 8 qualify() path covers these; add the `known_columns` fallback branch for an unexpanded star if it does not already fire.
4. Verify tests pass (GREEN). Commit: "feat(lineage): resolve qualified stars against plain tables"

**Done when:**
- [ ] `SELECT a.* FROM raw.a AS a` returns all of `raw.a`'s columns.
- [ ] A star whose table is absent from the mapping falls back to `known_columns`.
- [ ] A zero-column source yields a result with no `"*"` key and does not raise.
- [ ] Unparseable SQL returns `{}` and raises nothing, with the qualify() call unable to change that.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — fallback branch
- `tests/lineage/test_column_parser.py` — three tests

**Dependencies:** Task 8

---

### Task 10: Multi-star joins resolve each star against its own source
**Story:** Story 2, happy paths 1-3
**Type:** happy-path

**Steps:**
1. Write failing test: `SELECT a.*, b.* FROM raw.a AS a JOIN raw.b AS b ON a.id = b.id` returns keys `{id, x, y}` — never `{}`.
2. Write a failing three-way-join test.
3. Verify tests fail (RED).
4. Confirm qualify() handles both; adjust only if the expansion drops a source.
5. Verify tests pass (GREEN). Commit: "feat(lineage): resolve multi-star joins per source"

**Done when:**
- [ ] The case-2 SQL returns keys `{id, x, y}`.
- [ ] `x` maps to `(raw.a, x)` and `y` maps to `(raw.b, y)`.
- [ ] A three-way join reports columns from all three sources.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — only if expansion needs adjustment
- `tests/lineage/test_column_parser.py` — join tests

**Dependencies:** Task 9

---

### Task 11: Duplicate output names collapse to the first source, logged at debug
**Story:** Story 2, negative path 1
**Type:** negative-path

**Steps:**
1. Write failing test: a join where both sources carry `id` yields `id` exactly once, resolving to `raw.a`, and emits a debug log record naming the collapsed column.
2. Verify test fails (RED).
3. Deduplicate `output_columns` preserving first-seen order; call `logger.debug` once per collapsed name.
4. Verify test passes (GREEN) using `caplog` at `DEBUG`. Commit: "fix(lineage): collapse duplicate star output names to the first source"

**Done when:**
- [ ] `id` appears exactly once in the result and resolves to `raw.a`.
- [ ] A `DEBUG` record naming the duplicated column is captured by `caplog`.
- [ ] No column is traced twice for the same output name.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — dedupe plus debug log
- `tests/lineage/test_column_parser.py` — duplicate-name test

**Dependencies:** Task 10

---

### Task 12: Partial and unresolvable joins degrade without raising
**Story:** Story 2, negative paths 2, 3 and 4
**Type:** negative-path

**Steps:**
1. Write failing tests: one join side resolvable and one absent still reports the resolvable side; neither side resolvable with no `known_columns` returns `{}` with no `"*"` key; a timed-out column is omitted while traced columns are returned.
2. Verify tests fail (RED).
3. Implement or confirm the degradation paths.
4. Verify tests pass (GREEN). Commit: "fix(lineage): degrade gracefully on partially resolvable joins"

**Done when:**
- [ ] A half-resolvable join returns the resolvable side's columns and does not raise.
- [ ] A fully unresolvable join returns `{}` containing no `"*"` key.
- [ ] A per-column timeout omits only that column.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — degradation handling
- `tests/lineage/test_column_parser.py` — three negative-path tests

**Dependencies:** Task 11

---

### Task 13: Qualified-star EXCLUDE drops the excluded columns
**Story:** Story 3, all happy and negative paths
**Type:** happy-path

**Steps:**
1. Write failing tests: `SELECT a.* EXCLUDE (x) FROM raw.a AS a` yields `id` and not `x`; bare `SELECT * EXCLUDE (x)` is unchanged; `EXCLUDE (nonexistent)` returns all real columns; excluding every column returns empty with no `"*"` key; an unsupported dialect returns `{}`.
2. Verify tests fail (RED).
3. Confirm qualify() applies EXCLUDE; simplify or delete `_get_excluded_columns` if qualify() now covers it.
4. Verify tests pass (GREEN). Commit: "fix(lineage): honour EXCLUDE on qualified stars"

**Done when:**
- [ ] `x` is absent and `id` present for qualified-star EXCLUDE.
- [ ] Bare-star EXCLUDE behaviour is asserted unchanged.
- [ ] Excluding every column yields an empty result with no `"*"` key.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — EXCLUDE handling
- `tests/lineage/test_column_parser.py` — five EXCLUDE tests

**Dependencies:** Task 12

---

### Task 14: Delete _resolve_star_from_cte
**Story:** Story 1 and Story 5 — surviving behaviour is star expansion via qualify()
**Type:** refactor

**Steps:**
1. Remove `_resolve_star_from_cte` and its call site in `parse_column_lineage`.
2. Run `pytest`.
3. Confirm the existing CTE star-expansion tests still pass on the qualify() path — the surviving observable behaviour is that `SELECT * FROM cte` still resolves its columns.
4. Commit: "refactor(lineage): drop the hand-rolled CTE star resolver"

**Done when:**
- [ ] `pytest` passes with zero failures.
- [ ] The pre-existing `SELECT * FROM cte` tests still assert resolved column names.
- [ ] `parse_column_lineage` contains no call to a hand-rolled CTE star resolver.

**Files likely touched:**
- `src/docglow/lineage/column_parser.py` — delete function and call site

**Dependencies:** Task 13

---

### Task 15: Verify example-project lineage quality and benchmark cost
**Story:** Story 5 happy paths 2-4; Story 6 happy path 2
**Type:** verification

**Steps:**
1. Record traced-column counts for jaffle-shop and flowstate before and after the change.
2. Assert the after count is not lower for either project, and that no lineage entry is keyed `"*"`.
3. Add a test asserting the improved leaf attribution: `WITH r AS (SELECT id FROM raw.src) SELECT r.id AS id FROM r` resolves `id` to `raw.src`, not a bare `id`.
4. Add a test that an on-disk cache entry written by an older docglow version containing a `"*"` key is discarded on version change and the regenerated entry carries no `"*"` key.
5. Run `scripts/bench_column_lineage.py` against flowstate and record the result.
6. Commit: "test(lineage): assert example-project lineage quality and record benchmark"

**Done when:**
- [ ] Traced-column counts for both example projects are recorded and neither decreased.
- [ ] A passing test asserts `id` resolves to source table `raw.src` for the CTE case.
- [ ] No lineage entry across either example project is keyed `"*"`.
- [ ] A test proves a stale cache entry carrying a `"*"` key is regenerated without it on a version change.
- [ ] `scripts/bench_column_lineage.py` output is recorded in the PR description and is within 10% of the pre-change baseline.

**Files likely touched:**
- `tests/lineage/test_column_parser.py` — leaf-attribution test
- `tests/test_column_lineage_parallel.py` — example-project count assertions
- `tests/lineage/test_analyzer.py` — stale-cache regeneration test

**Dependencies:** Task 14

---

## Task Dependency Graph

```
Task 1 (type alias)
  └─ Task 2 (nested build_schema_mapping)
       ├─ Task 3 (omit malformed nodes) ─┐
       ├─ Task 4 (same-name coexistence) ┤
       └─ Task 5 (type annotations) ─────┤
                                         └─ Task 6 (migrate tests + worker transport)
                                              └─ Task 7 (literal-star guard)
                                                   └─ Task 8 (qualify() expansion)
                                                        └─ Task 9 (star against plain table)
                                                             └─ Task 10 (multi-star joins)
                                                                  └─ Task 11 (duplicate names)
                                                                       └─ Task 12 (partial joins)
                                                                            └─ Task 13 (EXCLUDE)
                                                                                 └─ Task 14 (delete resolver)
                                                                                      └─ Task 15 (quality + benchmark)
```

Acyclic. Tasks 3, 4 and 5 are mutually independent and may run in parallel; everything else is
strictly linear. Phase 1 is Tasks 1-6; Phase 2 is Tasks 7-15.

## Integration Points

- **After Task 6** — the nested mapping is live end to end, including the worker process boundary. Existing lineage can be regenerated and compared against the pre-change baseline; leaf attribution should already be better.
- **After Task 8** — the first reported failing case (case 1) is fixed and observable via `docglow generate`.
- **After Task 13** — all three star forms (qualified single-source, multi-star join, qualified EXCLUDE) resolve.

## Coverage Mapping

| Story | Criteria | Covering tasks |
|---|---|---|
| Story 1 | 4 happy, 4 negative | 7, 8, 9 |
| Story 2 | 3 happy, 4 negative | 10, 11, 12 |
| Story 3 | 2 happy, 3 negative | 13 |
| Story 4 | 3 happy, 5 negative | 1, 2, 3, 4, 5, 6 |
| Story 5 | 4 happy, 3 negative | 6, 15 |
| Story 6 | 2 happy, 3 negative | 7, 15 |

## Verification

- [ ] All happy path criteria covered by at least one task
- [ ] All negative path criteria covered by at least one task
- [ ] No task exceeds 5 minutes of work
- [ ] Every task has a `Done when:` block of falsifiable checks
- [ ] Dependencies are explicit and acyclic
