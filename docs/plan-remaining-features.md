# Implementation Plan: Remaining Feature Gaps (Phases 4-7)

## Overview

Eleven feature gaps remain after completed Phases 1-3 (MVP, Profiling & Health, AI Chat). Grouped into four phases by domain.

## Execution Order

1. AI context tiers (Phase 6.5)
2. --select/--exclude filtering (Phase 6.3)
3. datum.yml config file (Phase 6.1-6.2)
4. Lineage filtering + highlighting (Phase 5.1-5.4)
5. Histograms + patterns (Phase 4)
6. Mini-map (Phase 5.5-5.6)
7. BYOK env/CLI (Phase 6.4)
8. --watch flag (Phase 6.6)
9. Frontend packaging (Phase 7)

---

## Phase 4: Profiling Depth

### 4.1: Histogram bin SQL generation
- **File:** `src/docs_plus_plus/profiler/queries.py`
- Add `build_histogram_query()` using `WIDTH_BUCKET(col, min, max, 10)` for DuckDB/Postgres/Snowflake
- Returns bin_index, bin_low, bin_high, count per bin
- Min/max values already computed in stats query (second pass)

### 4.2: Pattern sample SQL generation
- **File:** `src/docs_plus_plus/profiler/queries.py`
- Add `build_pattern_sample_query()` using `REGEXP_REPLACE` to convert values to patterns (digits→N, alpha→X)
- GROUP BY pattern, ORDER BY COUNT DESC, LIMIT 5
- Returns pattern, example value, frequency

### 4.3: Execute histogram and pattern queries in engine
- **File:** `src/docs_plus_plus/profiler/engine.py`
- After main stats + top_values queries, add two more optional passes:
  - Numeric columns: histogram query using computed min/max
  - String columns: pattern sample query
- Store as `histogram` and `pattern_sample` in column profile dict
- **Depends on:** 4.1, 4.2

### 4.4: Stats parser extensions
- **File:** `src/docs_plus_plus/profiler/stats.py`
- Add `parse_histogram_rows()` → `[{bin_low, bin_high, count}]`
- Add `parse_pattern_sample_rows()` → `[{pattern, example, frequency}]`

### 4.5: TypeScript type extensions
- **File:** `frontend/src/types/index.ts`
- Add to `ColumnProfile`: `histogram?: HistogramBin[] | null`, `pattern_sample?: PatternSample[] | null`
- Add `HistogramBin` and `PatternSample` interfaces

### 4.6: Sparkline histogram component
- **File:** `frontend/src/components/models/Histogram.tsx` (new)
- Inline sparkline (~120x32px) and larger expanded version
- Simple SVG bars, tooltip shows bin range and count

### 4.7: Integrate into ColumnTable
- **File:** `frontend/src/components/models/ColumnTable.tsx`
- Numeric columns: render Histogram in ProfileDetail
- String columns: render pattern table in ProfileDetail
- **Depends on:** 4.5, 4.6

### 4.8: Tests
- Unit tests for SQL generation (all adapters), stats parsing

---

## Phase 5: Lineage Interactivity

### 5.1: Graph traversal utilities
- **File:** `frontend/src/utils/graphTraversal.ts` (new)
- `getUpstream(nodeId, edges)` → BFS backward traversal
- `getDownstream(nodeId, edges)` → BFS forward traversal
- `getFullChain(nodeId, edges)` → union of upstream + downstream + self

### 5.2: Filter toolbar
- **File:** `frontend/src/components/lineage/LineageFilters.tsx` (new)
- Search input (fuzzy match with Fuse.js)
- Tag multi-select, folder multi-select, resource type toggles
- Emits filtered node ID set

### 5.3: Full-chain hover highlighting
- **File:** `frontend/src/components/lineage/LineageGraph.tsx`
- Replace 1-hop adjacency with `getFullChain()` from 5.1
- Highlight edges connecting highlighted nodes; dim others
- **Depends on:** 5.1

### 5.4: Wire filters into lineage
- **File:** `frontend/src/components/lineage/LineageGraph.tsx`
- Filter nodes/edges before passing to `useLineageLayout`
- Debounce search input (300ms), immediate for dropdowns
- **Depends on:** 5.2, 5.3

### 5.5: Mini-map component
- **File:** `frontend/src/components/lineage/LineageMiniMap.tsx` (new)
- Small SVG overlay (150x100px) in bottom-left corner
- Shows scaled-down DAG + viewport rectangle
- Click-to-pan support

### 5.6: Integrate mini-map
- **File:** `frontend/src/components/lineage/LineageGraph.tsx`
- Render as overlay, pass layout/pan/zoom data, wire onNavigate
- **Depends on:** 5.5

---

## Phase 6: Configuration & CLI Infrastructure

### 6.1: datum.yml config file loading
- **File:** `src/docs_plus_plus/config.py`
- Add `load_config(project_dir)` → `DatumConfig`
- Parse `datum.yml` via pyyaml, validate with Pydantic
- Support: title, theme, health weights, naming rules, complexity thresholds, profiling settings, AI settings
- Add `pyyaml` to dependencies

### 6.2: Wire config into CLI and generation
- **Files:** `cli.py`, `site.py`, `data.py`
- Call `load_config()` in generate command
- Pass config through to `build_datum_data` and `compute_health`
- CLI flags override config file values
- **Depends on:** 6.1

### 6.3: --select/--exclude model filtering
- **File:** `src/docs_plus_plus/generator/data.py`
- Add `filter_models()` with glob patterns and `+` prefix/suffix for graph-aware selection
- Wire existing CLI flags through `generate_site` to `build_datum_data`

### 6.4: BYOK via env var and CLI flag
- **Files:** `cli.py`, `data.py`, `chatStore.ts`
- Resolution: `--ai-key` > `ANTHROPIC_API_KEY` env > datum.yml > UI input
- **Security**: Print CLI warning about embedded keys, never embed in --static without confirmation

### 6.5: AI context size tiers
- **File:** `src/docs_plus_plus/ai/context.py`
- ≤200 models: columns + description (current)
- 201-500: description only, omit columns
- 500+: omit both columns and description

### 6.6: --watch flag on serve
- **Files:** `cli.py`, `server/dev.py`, `server/watcher.py` (new)
- Polling-based (2s interval) on target/*.json files
- Debounce 3s cooldown, trigger `generate_site`
- Run watcher in background thread

### 6.7: Tests
- Config loading, model filtering, AI context tiers

---

## Phase 7: Distribution & Packaging

### 7.1: Build script
- **File:** `scripts/build_frontend.py` (new)
- Run `npm run build`, copy `frontend/dist/*` → `src/docs_plus_plus/static/`

### 7.2: Package configuration
- **File:** `pyproject.toml`
- Verify hatchling includes `static/` in wheel
- Add `.gitignore` for `src/docs_plus_plus/static/`

### 7.3: CI integration
- npm build → copy assets → python wheel build

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Embedded API key in static files | **High** | CLI warning, block in --static mode |
| Histogram queries slow on large tables | Medium | Opt-in via config, skip >1M rows |
| Lineage re-layout on filter | Medium | Debounce 300ms, memoize |
| File watcher cross-platform | Medium | Polling, not OS events |

---

## Dependency Graph

```
Phase 4:  4.1 ─┐
          4.2 ─┤
          4.4 ─┼─> 4.3 ─> 4.7
          4.5 ─┼─> 4.6 ─┘
          4.8 (parallel)

Phase 5:  5.1 ─> 5.3 ─┐
          5.2 ────────┼─> 5.4
          5.5 ─> 5.6   (independent)

Phase 6:  6.1 ─> 6.2
          6.3, 6.4, 6.5, 6.6 (independent)
          6.7 (after 6.1, 6.3, 6.5)

Phase 7:  7.1 ─> 7.2 ─> 7.3 (do last)
```
