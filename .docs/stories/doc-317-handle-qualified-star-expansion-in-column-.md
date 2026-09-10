**Status:** Accepted

# Stories: DOC-317 qualified star expansion in column lineage

Technical track — no PRD. Acceptance criteria are derived from the technical intent and the
APPROVED `adr-2026-09-10-nested-schema-mapping-for-star-expansion`, and they carry the five binding
conditions from `architecture-review-2026-09-10-doc-317-qualified-star-expansion`.

Behaviour throughout is observed through the public surface of
`docglow.lineage.column_parser` — `parse_column_lineage` and `build_schema_mapping`.

---

## Story 1: Qualified star with a single source resolves every column

**Requirement:** DOC-317 reported case 1; review condition 2

As a dbt project author, I want a model that projects `renamed.*` alongside an expression to
report lineage for every output column, so that column lineage is not silently empty for the
most common dbt staging pattern.

### Acceptance Criteria

#### Happy Path
- Given the SQL `WITH renamed AS (SELECT id, company FROM raw.src) SELECT md5(company) AS sk, renamed.* FROM renamed` and a nested schema containing `raw.src`, when `parse_column_lineage` runs, then the result contains keys `sk`, `id`, and `company`.
- Given that same SQL, when `parse_column_lineage` runs, then `id` maps to a dependency on source table `raw.src` column `id`, and `company` maps to `raw.src` column `company`.
- Given that same SQL, when `parse_column_lineage` runs, then `sk` still maps to `raw.src` column `company` with transformation `derived`, unchanged from current behaviour.
- Given a qualified star written against a table rather than a CTE (`SELECT a.* FROM raw.a AS a`), when `parse_column_lineage` runs, then every column of `raw.a` appears in the result.

#### Negative Paths
- Given the SQL `SELECT renamed.* FROM renamed` where `renamed` resolves to no CTE and no schema entry, when `parse_column_lineage` runs, then the returned dict contains no key equal to the literal string `*`, and the call returns without raising.
- Given a qualified star whose source table is absent from the schema mapping but whose columns are supplied via `known_columns`, when `parse_column_lineage` runs, then the catalog fallback supplies the output column names and lineage is attempted for each.
- Given SQL that SQLGlot cannot parse at all, when `parse_column_lineage` runs, then it returns an empty dict and does not raise.
- Given a qualified star against a source whose schema entry exists but lists zero columns, when `parse_column_lineage` runs, then the result contains no literal `*` key and the call returns without raising.

### Done When
- [ ] `parse_column_lineage` on the case-1 SQL returns exactly the keys `{sk, id, company}`.
- [ ] A unit test asserts `id` → `(raw.src, id)` and `company` → `(raw.src, company)`.
- [ ] A unit test asserts `"*" not in result` for an unresolvable qualified star.
- [ ] The existing case-1 behaviour for `sk` is covered by an assertion so it cannot silently regress.

---

## Story 2: Multi-star joins resolve each star against its own source

**Requirement:** DOC-317 reported case 2; review conditions 1 and 2

As a dbt project author, I want `select a.*, b.* from a join b` to report lineage for the columns
of both sources, so that join models are not left with no column lineage at all.

### Acceptance Criteria

#### Happy Path
- Given the SQL `SELECT a.*, b.* FROM raw.a AS a JOIN raw.b AS b ON a.id = b.id` where `raw.a` has columns `id, x` and `raw.b` has columns `id, y`, when `parse_column_lineage` runs, then the result contains keys `id`, `x`, and `y`.
- Given that same SQL, when `parse_column_lineage` runs, then `x` maps to a dependency on `raw.a` column `x`, and `y` maps to `raw.b` column `y`.
- Given a three-way join projecting three qualified stars, when `parse_column_lineage` runs, then columns from all three sources appear in the result.

#### Negative Paths
- Given the SQL above where both `raw.a` and `raw.b` carry a column named `id`, when `parse_column_lineage` runs, then `id` appears exactly once in the result, resolves to `raw.a` (the first projected source), and a debug-level log records that a duplicate output column name was collapsed.
- Given a join where one side is present in the schema mapping and the other is absent, when `parse_column_lineage` runs, then columns from the resolvable side are still reported and the call returns without raising.
- Given a join where neither side is present in the schema mapping and no `known_columns` are supplied, when `parse_column_lineage` runs, then the result contains no literal `*` key and the call returns an empty dict rather than raising.
- Given a join whose stars expand to more columns than the per-column trace timeout allows, when `parse_column_lineage` runs, then columns that timed out are omitted and the successfully traced columns are still returned.

### Done When
- [ ] `parse_column_lineage` on the case-2 SQL returns keys `{id, x, y}` — never `{}`.
- [ ] A unit test asserts the duplicate `id` appears exactly once and resolves to `raw.a`.
- [ ] A unit test asserts a partially-resolvable join still returns the resolvable side.
- [ ] No result from any join scenario contains the literal key `*`.

---

## Story 3: Qualified-star EXCLUDE omits the excluded columns

**Requirement:** Review condition 2

As a dbt project author on a warehouse supporting `EXCLUDE`, I want `a.* EXCLUDE (x)` to drop `x`
from the reported lineage, so that lineage reflects the columns the model actually produces.

### Acceptance Criteria

#### Happy Path
- Given the SQL `SELECT a.* EXCLUDE (x) FROM raw.a AS a` where `raw.a` has columns `id, x`, when `parse_column_lineage` runs, then the result contains key `id` and does not contain key `x`.
- Given a bare `SELECT * EXCLUDE (x) FROM raw.a`, when `parse_column_lineage` runs, then `x` is likewise absent, preserving today's behaviour for the unqualified form.

#### Negative Paths
- Given `SELECT a.* EXCLUDE (nonexistent) FROM raw.a AS a`, when `parse_column_lineage` runs, then all real columns of `raw.a` are reported and the call returns without raising.
- Given `EXCLUDE` used against a dialect that does not support it, when parsing fails, then `parse_column_lineage` returns an empty dict and does not raise.
- Given `SELECT a.* EXCLUDE (id, x) FROM raw.a AS a` excluding every column, when `parse_column_lineage` runs, then the result is empty and contains no literal `*` key.

### Done When
- [ ] A unit test asserts `x` is absent and `id` present for qualified-star EXCLUDE.
- [ ] A unit test asserts the pre-existing bare-star EXCLUDE behaviour is unchanged.
- [ ] Excluding every column yields an empty result rather than a literal `*` key.

---

## Story 4: The schema mapping is uniform depth and never raises

**Requirement:** ADR decisions 1 and 3; review conditions 3 and 4 (High-impact risk)

As a docglow user generating a site, I want a malformed node in the manifest to cost at most that
node's lineage, so that one incomplete model cannot remove column lineage from the whole project.

### Acceptance Criteria

#### Happy Path
- Given models and sources carrying `database`, `schema`, and `name`, when `build_schema_mapping` runs, then the returned mapping is nested `database → schema → table → column`, and `raw.a`'s columns are reachable at that path.
- Given the returned mapping, when it is passed to SQLGlot's `MappingSchema`, then the reported nesting depth is 3 and no error is raised.
- Given a mapping built from the jaffle-shop example manifest and catalog, when column lineage runs end to end, then every model that traced successfully before this change still traces successfully.

#### Negative Paths
- Given a node missing `database`, when `build_schema_mapping` runs, then that node is omitted from the mapping entirely, every other node is still present, and the mapping remains uniform depth 3.
- Given a node missing `schema`, when `build_schema_mapping` runs, then that node is omitted and the mapping remains uniform depth 3.
- Given a mapping containing at least one omitted node, when the mapping is handed to `MappingSchema`, then no `SchemaError` about mismatched nesting level is raised.
- Given a node omitted from the mapping whose columns are known from the catalog, when `parse_column_lineage` runs for that model, then the `known_columns` fallback supplies the output columns and lineage is still attempted.
- Given two tables sharing a name in different schemas, when `build_schema_mapping` runs, then both are present at their distinct paths and neither overwrites the other.

### Done When
- [ ] `build_schema_mapping` returns a nested mapping; `MappingSchema(result).depth()` equals 3.
- [ ] A unit test proves a node missing `database` or `schema` is omitted and the mapping still constructs without raising.
- [ ] A unit test proves two same-named tables in different schemas coexist.
- [ ] All six existing call sites asserting the flat shape are migrated: 6 in `tests/lineage/test_column_parser.py`, 2 in `tests/test_column_lineage_parallel.py`, and the assertion in `tests/lineage/test_source_column_lineage.py`.
- [ ] `pytest` passes with no test still constructing or asserting a flat dotted mapping.

---

## Story 5: Existing lineage quality is preserved or improved, at no performance cost

**Requirement:** ADR consequences; review condition 5

As a docglow maintainer, I want the reshape to leave existing lineage at least as good and no
slower, so that fixing a rare bug does not degrade the common path.

### Acceptance Criteria

#### Happy Path
- Given `WITH r AS (SELECT id FROM raw.src) SELECT r.id AS id FROM r` and a nested schema, when `parse_column_lineage` runs, then `id` resolves to source table `raw.src` — the correct leaf attribution, rather than the bare `id` the flat mapping produced.
- Given the jaffle-shop example project, when column lineage runs end to end, then the count of successfully traced columns is greater than or equal to the count before this change.
- Given the flowstate example project, when column lineage runs end to end, then the count of successfully traced columns is greater than or equal to the count before this change.
- Given the column-lineage benchmark in `scripts/`, when it runs against the flowstate example on this change, then wall-clock time is within 10% of the pre-change baseline.

#### Negative Paths
- Given a model whose source is absent from the schema mapping and which has no `known_columns`, when `parse_column_lineage` runs, then it returns an empty dict without raising, exactly as before.
- Given the parallel `ProcessPoolExecutor` path, when the nested mapping is pickled to workers, then workers produce the same lineage as the serial path for the same model.
- Given a benchmark run showing a regression worse than 10%, when the result is reviewed, then the change is not merged until the regression is explained or removed.

### Done When
- [ ] A unit test asserts the improved leaf attribution (`raw.src`, not bare `id`) for the CTE case.
- [ ] Traced-column counts for jaffle-shop and flowstate are recorded before and after, and the after count is not lower for either.
- [ ] The `scripts/` column-lineage benchmark has been run on this change and the result recorded in the PR description.
- [ ] A test asserts the serial and parallel paths agree on the same model.

---

## Story 6: No literal star ever reaches a consumer as a column name

**Requirement:** Review condition 2; ADR decision 4 rationale

As a docglow user, I want no column named `*` to appear anywhere in the generated site or the
lineage cache, so that a parsing gap never surfaces as a fake column.

### Acceptance Criteria

#### Happy Path
- Given any SQL in which every star expands successfully, when `parse_column_lineage` runs, then no result key equals `*`.
- Given the jaffle-shop and flowstate example projects, when column lineage runs end to end, then no model's lineage contains a column named `*`.

#### Negative Paths
- Given SQL whose star cannot be expanded because `qualify` left it in place, when `parse_column_lineage` runs, then the unexpanded star is dropped rather than emitted as a column named `*`.
- Given SQL with a qualified star that cannot be expanded and no `known_columns`, when `parse_column_lineage` runs, then it returns an empty dict rather than a dict keyed by `*`.
- Given a model whose lineage was previously written to the on-disk cache with a `*` key by an older docglow version, when lineage is recomputed after a version change, then the regenerated entry contains no `*` key.

### Done When
- [ ] A unit test asserts `"*" not in result` for each unresolvable-star scenario in Stories 1, 2, and 3.
- [ ] An end-to-end assertion over both example projects confirms no lineage entry is keyed `*`.
