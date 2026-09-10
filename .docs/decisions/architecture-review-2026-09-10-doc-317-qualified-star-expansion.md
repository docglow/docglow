# Architecture Review: DOC-317 qualified star expansion in column lineage

**Date:** 2026-09-10
**Mode:** Lightweight (Medium tier) — Sections 2 and 4 only
**Track:** technical (no PRD)
**Input reviewed:** `.docs/track/`, `.docs/complexity/`, `.docs/architecture/` (stories and plan do
not exist yet)
**Verdict:** APPROVED WITH CONDITIONS

## Feasibility

| Check | Finding |
|---|---|
| Stack compatibility | **Pass.** `sqlglot.optimizer.qualify` ships in sqlglot 29.0.1, already a required extra (`docglow[column-lineage]`). No new dependency, no version bump. |
| Prerequisites | **None.** No migration, no config, no external account. The column-lineage cache is keyed by SQL hash plus docglow version, so no cache invalidation step is required. |
| Integration surface | **2 modules.** `column_parser.py` and `analyzer.py`. Crosses one process boundary — the mapping is pickled into ProcessPoolExecutor workers and held in the `_worker_schema` global. |
| Data implications | **No schema or migration.** The only shape change is in-memory and in the on-disk lineage cache, which regenerates on version change. |
| Performance risk | **Net favourable.** `qualify()` adds one AST pass per model, but the mapping shrinks ~3x (one key per table rather than three), reducing per-worker pickle payload. Confirm with the existing `scripts/` column-lineage benchmark before merge — a condition below. |
| Worktree isolation | **Not applicable.** No new service, port, database, or shared file. |

## Alignment

**Domain boundaries** — Clean. The change stays inside `lineage/`. `build_schema_mapping` and
`parse_column_lineage` keep their names, signatures, and return types; only the mapping's internal
shape changes. Nothing reaches across into `generator/`, `analyzer/`, or `profiler/`.

**Pattern consistency** — Consistent with the documented "SQLGlot for SQL parsing and column
lineage" stack choice in CLAUDE.md. The change moves *more* work to SQLGlot rather than less,
deleting hand-rolled resolution (`_resolve_star_from_cte`) in favour of the library's own name
resolver. No new structural pattern is introduced.

**State management** — No new state. `_worker_schema` remains a module global populated once per
worker; its shape changes, its lifecycle does not.

**Diagram accuracy** — `.docs/architecture/components.md` and
`.docs/architecture/sequences/star-expansion.md` were authored for this change and reviewed
against it. Both render (`conduct render-diagrams --check` exits 0). No other diagrams exist.

**Security boundaries** — No new endpoint, input, or credential. Compiled SQL is already parsed by
this code path; `qualify()` operates on the same already-trusted AST and reaches no network or
filesystem.

**Production DI defaults** — Not applicable. No dependency injection or persistent store.

## Wiring Surface

No new production surface is introduced. All changed code is reached through existing call sites:

| Surface | Called from in production |
|---|---|
| `qualify()` invocation | Inside `parse_column_lineage`, already invoked at `analyzer.py:171` (serial path) and from the worker entry point that reads `_worker_schema` (parallel path). |
| `build_schema_mapping` (reshaped return) | `analyzer.py:272` and `analyzer.py:406`, both existing. |
| Star-shape guard | Inside `_extract_output_columns`, called only by `parse_column_lineage`. |
| `_resolve_star_from_cte` | **Removed.** Its only caller is `parse_column_lineage`, which drops the call. |

## Risks

| Risk | Type | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Reshape silently degrades resolution on an unmeasured adapter that emits bare or two-part table references | Technical | Low | Medium | `known_columns` catalog fallback is retained specifically for this. Add a test asserting the fallback fires when a table is absent from the mapping. |
| Node missing `database` or `schema` produces a mixed-depth mapping, raising `SchemaError` and killing lineage project-wide | Technical | Low | **High** | ADR decision 3 omits such nodes rather than inserting them at a shorter depth. Requires an explicit test — a mixed-depth mapping must never be constructible. |
| Six existing test call sites assert the flat shape; a partial migration leaves the suite green but the mapping wrong | Knowledge | Medium | Medium | Migrate all six in the same change; the reshape is not complete while any test still constructs a flat mapping. |
| Neither bundled example exercises an outermost qualified star, so no fixture guards the fixed behaviour | Knowledge | **High** | Medium | The fix must ship with its own unit tests covering both reported cases. Measured: 0 of 445 models across jaffle-shop and flowstate use a qualified star in the outermost projection. |
| Duplicate output column names from multi-star joins collide in the dict-keyed result | Technical | Medium | Medium | Unresolved — see Conditions. Must be decided in stories, not defaulted. |

## ADRs Created

- `adr-2026-09-10-nested-schema-mapping-for-star-expansion` — canonical three-part nesting for the
  lineage schema mapping. Meets the structural prerequisite: it fixes the canonical addressing
  scheme for table identity across a module and process seam and revises the integration pattern
  with the SQLGlot `MappingSchema` boundary. No existing ADR governs it (`.docs/decisions/` was
  empty before this review).

The duplicate-column-name question is deliberately **not** an ADR. It is an output-shaping
behaviour, not a structural decision — no boundary, decomposition, integration seam, data
architecture, or foundational technology changes with it.

## Conditions

1. **Decide duplicate-name handling in stories, explicitly.** `SELECT a.*, b.*` where both sources
   carry `id` yields two `id` projections; the result is a `dict` keyed by column name, so one
   silently overwrites the other. Stories must state the chosen behaviour — merge dependencies
   from both sources, or keep the first and log at debug. Do not let the dict-overwrite default
   stand unexamined.
2. **Ship tests for both reported cases.** `select md5(company) as sk, renamed.*` and
   `select a.*, b.* from a join b`, plus qualified-star `EXCLUDE`, plus an assertion that no
   literal `'*'` ever appears as an output column name. No existing fixture covers any of these.
3. **Migrate all six flat-shape test call sites in the same change.** `tests/lineage/test_column_parser.py`
   (6 sites), `tests/test_column_lineage_parallel.py` (2 sites), and the assertion in
   `tests/lineage/test_source_column_lineage.py`.
4. **Assert the mixed-depth guard.** A node missing `database` or `schema` must be omitted, and a
   test must prove the resulting mapping is uniform-depth and does not raise.
5. **Run the existing column-lineage benchmark in `scripts/` before merge** and confirm no
   regression, given the added `qualify()` pass per model.

## Blocking Issues

None.
