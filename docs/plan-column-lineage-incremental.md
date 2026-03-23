# Implementation Plan: Incremental Column Lineage

## Overview

Running `--column-lineage` on a large project (1,500+ models) is slow because every model's SQL gets parsed with sqlglot (each column trace uses a thread with a 2-second timeout). This plan adds `--column-lineage-select` to analyze only models within a subgraph, letting users get value incrementally. The existing cache (`.docglow-column-lineage-cache.json`) means results accumulate across runs.

## Requirements

- Users can specify a starting model and direction to limit which models get column-lineage-parsed
- The syntax reuses the existing `+name` / `name+` convention from `--select`
- An optional depth limit caps the number of hops traversed
- Cached results from previous runs are always included in output, even for models outside the current subset
- The feature works correctly alongside `--select` / `--exclude` (independent concerns)

## Architecture Changes

- **`src/docglow/cli.py`**: Two new flags (`--column-lineage-select`, `--column-lineage-depth`)
- **`src/docglow/lineage/analyzer.py`**: New `compute_column_lineage_subset()` function; new `subset` parameter on `analyze_column_lineage()`
- **`src/docglow/generator/data.py`**: New params on `build_docglow_data()`, subset computation before calling analyzer
- **`src/docglow/generator/site.py`**: Pass-through of new params to `build_docglow_data()`

## Implementation Steps

### Phase 1: CLI Flags

#### 1. Add `--column-lineage-select` flag
**File:** `src/docglow/cli.py` (after `--column-lineage`)

- Add Click option: `--column-lineage-select`, type `str`, default `None`
- Help text: `"Only analyze column lineage for this model and its dependencies (e.g. fct_orders, +fct_orders, fct_orders+)"`

#### 2. Add `--column-lineage-depth` flag
**File:** `src/docglow/cli.py`

- Add Click option: `--column-lineage-depth`, type `int`, default `None`
- Help text: `"Max number of hops from the selected model (default: unlimited)"`

#### 3. Validate flag combinations
**File:** `src/docglow/cli.py` (in `generate()` body)

- `--column-lineage-select` implies `--column-lineage` (same pattern as `--ai-key` implies `--ai`)
- `--column-lineage-depth` without `--column-lineage-select` prints an error and exits

### Phase 2: Subgraph Computation

#### 4. Create `compute_column_lineage_subset()` function
**File:** `src/docglow/lineage/analyzer.py`

```python
def compute_column_lineage_subset(
    pattern: str,
    models: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    seeds: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    max_depth: int | None = None,
) -> set[str]:
```

Behavior:
1. Parse `+` prefix/suffix to determine direction
2. Strip `+` from pattern, match model names using `fnmatch` (same as `_resolve_selection` in `data.py`)
3. BFS walk in the determined direction(s) using `depends_on` (upstream) and `referenced_by` (downstream)
4. Respect `max_depth` if provided
5. Return set of unique_ids to analyze

#### 5. Direction semantics

| Pattern | Direction | Rationale |
|---------|-----------|-----------|
| `fct_orders` | upstream only | Default. Column lineage traces origins, so upstream is natural. |
| `+fct_orders` | upstream only | Explicit upstream (same as default). |
| `fct_orders+` | downstream only | "What consumes this model's columns?" |
| `+fct_orders+` | both directions | Full neighborhood. |

#### 6. Depth-limited BFS

Use BFS (not DFS) to respect depth limits correctly. BFS guarantees shortest-path depth, so depth=2 means exactly 2 hops.

### Phase 3: Integration with Analyzer

#### 7. Add `subset` parameter to `analyze_column_lineage()`
**File:** `src/docglow/lineage/analyzer.py`

Add optional parameter: `subset: set[str] | None = None`

In the main loop, add early filtering:
```python
if subset is not None and uid not in subset:
    # Include cached results for models outside the subset
    cached_entry = cache.get(uid)
    if cached_entry and cached_entry.get("lineage"):
        column_lineage[uid] = cached_entry["lineage"]
    continue
```

**Key design decision:** Models outside the subset skip SQL parsing but their cached results still appear in the output. The full cache dict is always saved back to disk.

#### 8. Subset logging

When subset is active, log: `Column lineage: analyzing 47/1587 models (subset selection active)`

### Phase 4: Plumbing

#### 9. Thread params through `build_docglow_data()`
**File:** `src/docglow/generator/data.py`

Add parameters: `column_lineage_select: str | None = None`, `column_lineage_depth: int | None = None`

Before calling `analyze_column_lineage`, compute the subset using `compute_column_lineage_subset`.

#### 10. Thread params through `generate_site()`
**File:** `src/docglow/generator/site.py`

Add pass-through parameters.

#### 11. Pass CLI values to `generate_site()`
**File:** `src/docglow/cli.py`

Wire the new CLI flag values into the `generate_site()` call.

## Interaction with `--select` / `--exclude`

These are independent concerns:

| Flag | What it controls | Where it's applied |
|------|------------------|--------------------|
| `--select` / `--exclude` | Which models appear in the generated site | `data.py` (after all data is built) |
| `--column-lineage-select` | Which models get SQL-parsed for column lineage | `analyzer.py` (inside `analyze_column_lineage`) |

A user can use both simultaneously. Column lineage results live in a separate `column_lineage` key in the output, so even if some upstream models are excluded by `--select`, their column lineage data is still available.

## UX Decisions

1. **Default direction is upstream-only.** Column lineage traces where columns come from, so upstream is the natural default.
2. **`--column-lineage-select` implies `--column-lineage`.** No need to type both flags.
3. **No depth limit by default.** Most upstream subgraphs are naturally bounded (they converge on sources).
4. **Same pattern syntax as `--select`.** Globs (`fct_*`), folder paths, and direction operators (`+name`, `name+`) work identically.

## Cache Accumulation

This is the key insight: the existing cache mechanism makes incremental runs additive.

```bash
# First run: analyze one subgraph (~47 models)
docglow generate --column-lineage-select fct_orders

# Second run: analyze another subgraph (~30 models)
# Cache already has fct_orders subgraph, so those models are instant
docglow generate --column-lineage-select dim_customers

# The output site now has column lineage for BOTH subgraphs
# Models shared between subgraphs were parsed once and cached
```

Over time, the cache fills up. Eventually `docglow generate --column-lineage` (full run) becomes fast because most models are cached.

## Testing Strategy

### Unit Tests (`tests/lineage/test_analyzer.py`)

Test `compute_column_lineage_subset`:
- Simple upstream walk (model with 3 upstream parents)
- Simple downstream walk
- Both directions (`+model+`)
- Depth=1 returns only direct parents/children
- Glob pattern matching (`fct_*` matches multiple models)
- Model not found returns empty set
- Sources in `depends_on` are included in result

Test `analyze_column_lineage` with subset:
- Subset models get parsed, non-subset models skip parsing
- Cached results for non-subset models appear in output
- Empty subset produces output with only cached results

### Integration Tests
- `--column-lineage-select fct_orders` works (implies `--column-lineage`)
- `--column-lineage-depth 2` without `--column-lineage-select` exits with error

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `depends_on` contains IDs not in any resource dict | Low | BFS silently skips unknown IDs |
| Very large subgraphs still slow | Medium | `--column-lineage-depth` provides escape hatch. Cache ensures only first run is slow. |
| Race condition with concurrent cache writes | Low | Cache is best-effort optimization, not correctness requirement |

## Success Criteria

- [ ] `docglow generate --column-lineage-select fct_orders` analyzes only fct_orders and its upstream models
- [ ] `docglow generate --column-lineage-select "fct_orders+"` analyzes downstream models
- [ ] `docglow generate --column-lineage-select fct_orders --column-lineage-depth 2` limits to 2 hops
- [ ] Cached results from previous runs are preserved and included in output
- [ ] Running different subsets across multiple runs accumulates column lineage data
- [ ] `--column-lineage-select` implies `--column-lineage`
- [ ] Log output shows subset size vs total model count
- [ ] All existing tests pass unchanged
