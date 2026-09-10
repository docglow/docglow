# Conflict Check: DOC-317 qualified star expansion

**Date:** 2026-09-10
**Result:** PASSED CLEAN — zero blocking conflicts, zero degrading conflicts
**ADR corpus:** `change_set` (`conflict_check.adr_corpus` unset — default applied)

## Inventory

- Stories scanned: `.docs/stories/doc-317-handle-qualified-star-expansion-in-column-.md` — Stories 1 through 6.
  This is the only stories file in the repository; there is no pre-existing accepted story work to
  conflict with.
- ADRs compared: `adr-2026-09-10-nested-schema-mapping-for-star-expansion` (APPROVED). It is the
  only ADR in the change set and the only ADR in `.docs/decisions/`.
- Prior conflict reports: none — `.docs/conflicts/` did not exist before this run.

## Pairs examined

All 15 story pairs were checked. Every pair sharing a behaviour, entity, field, or gate was tested
in **both** directions ("if A is fully satisfied, does B still hold?") to separate an oscillation
from an ordinary contradiction. The shared surfaces are: the schema mapping shape, the
`known_columns` fallback, duplicate output column names, the literal-`*` guard, and `EXCLUDE`.

| Pair | Shared surface | Both directions hold? |
|---|---|---|
| 1 × 2 | literal-`*` guard, star expansion | Yes — different star shapes, identical assertion about `*` |
| 1 × 3 | qualified star, EXCLUDE | Yes — EXCLUDE narrows the same expansion Story 1 establishes |
| 1 × 4 | mapping shape | Yes — sequencing only (see below), no contradictory assertion |
| 1 × 5 | traced-column counts | Yes — Story 1 only adds columns, never removes |
| 1 × 6 | literal-`*` guard | Yes — Story 6 generalises Story 1's assertion, same direction |
| 2 × 3 | — | No shared surface |
| 2 × 4 | mapping shape | Yes — sequencing only |
| 2 × 5 | traced-column counts | Yes — join expansion only adds columns |
| 2 × 6 | literal-`*` guard | Yes — consistent |
| 3 × 4 | mapping shape | Yes — sequencing only |
| 3 × 5 | traced-column counts | Yes — see finding N-2 |
| 3 × 6 | literal-`*` guard | Yes — Story 3's exclude-everything case returns empty, not `*` |
| 4 × 5 | node omission vs count floor | Yes — see finding N-1 |
| 4 × 6 | mapping shape, `*` guard | Yes — consistent |
| 5 × 6 | traced-column counts | Yes — see finding N-3 |

## ADR versus stories

`adr-2026-09-10-nested-schema-mapping-for-star-expansion` was compared against every story that
touches the mapping shape or the fallback (Stories 1, 2, 3, 4, 5, 6). No opposing sentence pair was
found in either direction:

- ADR decision 1 (nested `database → schema → table`) is asserted directly by Story 4's Done-When
  (`MappingSchema(result).depth()` equals 3).
- ADR decision 3 (omit nodes missing `database` or `schema`) is asserted directly by Story 4's
  negative paths.
- ADR decision 4 (retain the `known_columns` fallback) is asserted by Story 1's and Story 4's
  negative paths.
- ADR consequence "improves existing tracing" is asserted by Story 5's first happy-path criterion.

No conflict recorded, because no grounded opposing-sentence pair exists.

## Non-blocking findings

**N-1 — Story 4 node omission versus Story 5 count floor (examined, not a conflict).**
Story 4 omits a node missing `database` or `schema`; Story 5 requires traced-column counts to be
greater than or equal to the pre-change baseline. In principle an omitted node could lower the
count. Verified empirically: **0 of 525 nodes and sources** across jaffle-shop (47) and flowstate
(478) lack `database` or `schema`, so the omission rule cannot fire on either project Story 5
measures. Story 4's `known_columns` fallback negative path is the compensating behaviour for any
project where it does fire. Both directions hold; this is not an oscillation. (verified, 95%)

**N-2 — Story 3 EXCLUDE versus Story 5 count floor (examined, not a conflict).**
Story 3 removes excluded columns from the result, which could in principle lower a count. It
cannot lower it against the stated baseline: a qualified-star EXCLUDE model traces to nothing today,
so any post-change result is an increase. Bare-star EXCLUDE, which already works, is explicitly
asserted unchanged by Story 3's second happy-path criterion.

**N-3 — Story 6 literal-`*` removal versus Story 5 count floor (examined, not a conflict).**
Removing `*` keys cannot lower the count, because no `*` key is ever recorded today:
`parse_column_lineage` inserts a key only when the trace returns dependencies, and a literal `*`
resolves to none.

## Sequencing dependency (plan input, not a conflict)

Story 4 establishes the nested depth-3 mapping that Stories 1, 2, 3, and 6 rely on for star
expansion. The dependency is **linear and acyclic** — Story 4 asserts nothing that depends on
Stories 1, 2, 3, or 6, so there is no circular sequencing conflict. It is recorded here so `/plan`
orders Story 4's tasks first; it is not a contradiction and requires no story change.

## Resolutions applied

None. No story text was changed by this check.
