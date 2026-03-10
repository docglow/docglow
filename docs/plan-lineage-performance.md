# Plan: Lineage Explorer Performance Tuning

## Context

Models with many edges/references (e.g. `fact_docket` with 145 referenced-by nodes) cause the lineage explorer to slow down. The root causes are: no virtualization, expensive layout recomputation on every interaction, per-edge style object creation, and unlimited-depth highlight traversal on hover.

## Current Bottlenecks (severity order)

| # | Bottleneck | Location | Impact |
|---|-----------|----------|--------|
| 1 | Dagre layout + layer alignment | `LineageFlow.tsx` `computeLayout()` (~300 lines) | Runs on every depth/filter/direction change, O(N log N) + custom alignment |
| 2 | No virtualization | `<ReactFlow>` renders all nodes/edges to DOM | 500+ nodes = 500+ DOM elements regardless of viewport |
| 3 | Per-edge style objects | `rfEdges` memo creates individual `style` + `markerEnd` per edge | 500 edges = 1000+ object allocations per highlight change |
| 4 | Unlimited highlight BFS | `getFullChain()` in `utils/graphTraversal.ts` | Traverses entire edge array with no depth cap on hover |
| 5 | Double subgraph computation | `LineagePage.tsx` calls `getSubgraph()` twice | Once for display, once for filter option extraction |

---

## Phase 1: Quick Wins

Low effort, medium impact. Can be done in a single session.

### 1.1 Debounce highlight on hover

- Add 50–100ms debounce to `setHoveredId` in `LineageFlow.tsx`
- Prevents BFS recomputation on every pixel of mouse movement
- Use a simple `setTimeout`/`clearTimeout` pattern (no new deps needed)

### 1.2 Cap highlight depth

- `getFullChain()` currently traverses the entire graph (unlimited depth)
- Limit traversal to match the current subgraph depth (e.g. depth 2–3)
- Add a `maxDepth` parameter to `getUpstream()`/`getDownstream()` in `graphTraversal.ts`

### 1.3 Shared SVG markers for edges

- Currently each edge creates its own `markerEnd` object with inline color
- Define 2–3 shared `<marker>` SVG defs (highlighted, default, dimmed) and reference by ID
- Eliminates ~500 object allocations for a 500-edge graph

### 1.4 Memoize `getFullChain` by nodeId

- Cache results in a `Map<string, Set<string>>` keyed by nodeId
- Clear cache when edges change (new subgraph)
- Re-hovering the same node becomes instant

### 1.5 Deduplicate subgraph computation

- In `LineagePage.tsx`, compute filter options from the already-computed subgraph nodes instead of calling `getSubgraph()` a second time
- `computeSubgraphOptions()` already takes nodes — just pass `rawSubgraph.nodes` once

---

## Phase 2: Biggest Bang

Medium effort, high impact. Core architectural improvements.

### 2.1 Cap subgraph size with auto-reduce

- If a given depth yields more than N nodes (e.g. 300), auto-reduce depth until under the threshold
- Show a toast/banner: "Reduced to depth N (too many nodes at depth M)"
- Prevents the DOM from ever rendering an unmanageable number of elements

### 2.2 Move layout to a Web Worker

- `computeLayout()` blocks the main thread during dagre + layer alignment
- Move to a dedicated Web Worker:
  - Post `{ nodes, edges, folderNodeIds }` to worker
  - Worker runs dagre + alignment, posts back `LayoutResult`
  - Main thread shows a lightweight skeleton/spinner during computation
- Keeps UI responsive during layout of large graphs

### 2.3 Cache layout results

- Key: hash of sorted node IDs + sorted edge pairs
- Store: `Map<string, LayoutResult>` (bounded LRU, e.g. 10 entries)
- Toggling filters back and forth reuses cached layouts instead of recomputing
- Combine with Web Worker — cache check happens before posting to worker

### 2.4 Stable node references to reduce React reconciliation

- Currently `rfNodes` creates new objects whenever `highlightedSet` changes (every hover)
- Split into stable position data (changes only on layout) and volatile visual data (changes on hover)
- Use React Flow's `nodeData` vs `style` separation so React doesn't diff 500 nodes on every hover
- Ensure `DagNode`/`FolderNode` are wrapped in `React.memo` with shallow comparison

---

## Phase 3: Long-Term

Higher effort, highest ceiling. For when the project scales to very large dbt projects.

### 3.1 Server-side pre-layout

- Compute dagre layout in Python during `docglow generate`
- Ship node positions in `docglow-data.json` alongside node metadata
- Frontend skips layout computation entirely — just renders at provided positions
- Layout still recomputed client-side for filtered/subgraph views, but full-project view is instant

### 3.2 Switch from dagre to elkjs

- ELK (Eclipse Layout Kernel) is faster than dagre for large layered graphs
- Native Web Worker support (`elkjs/lib/elk-worker.min.js`)
- Better layered layout algorithm that may eliminate some custom post-layout alignment code
- Breaking change to layout output format — test visually before committing

### 3.3 Canvas/WebGL rendering

- ReactFlow supports canvas-based rendering for large graphs
- Alternative: switch to `react-force-graph` or `Sigma.js` for WebGL
- DOM rendering hits a practical wall at 500–1000 nodes
- Trade-off: lose some CSS styling flexibility, gain 10x+ node capacity

### 3.4 Progressive disclosure / expand-on-demand

- Start with immediate neighbors only (depth 1)
- User clicks a node edge handle to expand one level outward from that node
- Keeps visible node count low regardless of graph complexity
- Requires UX design for expand/collapse affordances on nodes
