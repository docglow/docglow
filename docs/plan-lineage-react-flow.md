# Plan: React Flow + Folder-Level Lineage

> Option B — React Flow as rendering engine + folder aggregation for scalability.
> See also: plan-lineage-folder-aggregation.md for the Dagre-only approach.

## Requirements

Replace the custom SVG lineage renderer with React Flow (`@xyflow/react`), while implementing folder-level aggregation to handle 3,000+ node graphs. Small projects (< ~100 nodes) show the flat graph natively. Large projects show a folder-level DAG with click-to-expand. All existing features (highlighting, filtering, minimap, zoom, navigation) must be preserved.

## Architecture

```
LineagePage (filtering + expand/collapse state)
       │
  ┌────▼──────────────────────┐
  │ aggregateByFolder()        │  ← Folder aggregation utility
  │ + buildMixedGraph()        │
  └────┬──────────────────────┘
       │
  ┌────▼──────────────────────┐
  │ layoutWithDagre()          │  ← Dagre computes positions
  │ → React Flow node format   │  ← Convert to {id, position, data, type}
  └────┬──────────────────────┘
       │
  ┌────▼──────────────────────┐
  │ <ReactFlow>                │  ← @xyflow/react
  │   nodeTypes:               │
  │     model → <ModelNode>    │  ← Custom node component
  │     source → <SourceNode>  │
  │     folder → <FolderNode>  │  ← Expandable super-node
  │   <MiniMap />              │  ← Built-in plugin
  │   <Controls />             │  ← Built-in plugin
  └───────────────────────────┘
```

## Implementation Phases

### Phase 1: Install & Scaffold React Flow
**Files:** `package.json`, new `LineageFlow.tsx`

- Install `@xyflow/react`
- Keep `dagre` (still used for layout computation)
- Create `LineageFlow.tsx` alongside existing `LineageGraph.tsx` (no deletion yet)
- Scaffold basic `<ReactFlow>` wrapper with `<MiniMap />`, `<Controls />`, and `<Background />`
- Wire up Dagre layout → React Flow position format (center → top-left coordinate shift)
- Verify it renders the existing small test fixture identically

### Phase 2: Custom Node Components
**New files:** `frontend/src/components/lineage/nodes/ModelNode.tsx`, `SourceNode.tsx`, `FolderNode.tsx`

- **ModelNode**: Colored left bar by resource type, name, materialization label, test status border. Memoized with `React.memo`.
- **SourceNode**: Green accent, source-specific metadata
- **FolderNode**: Larger node (220×60), folder icon, name, count subtitle ("42 models, 5 sources"), expand/collapse chevron, click handler. Visually distinct.
- Register all via `nodeTypes` prop on `<ReactFlow>`
- Custom edge or default `SmoothStep` with animated option for highlighted edges

### Phase 3: Folder Aggregation Utility
**New file:** `frontend/src/utils/lineageAggregation.ts`

- `aggregateByFolder(nodes, edges)` → `{ folderNodes, folderEdges }`
- `buildMixedGraph(folderGraph, expandedFolders, originalNodes, originalEdges)`
- `shouldUseFolderView(nodes)` → boolean (threshold ~100)

### Phase 4: Wiring It Together in LineagePage
**Modify:** `LineagePage.tsx`

- Add `expandedFolders: Set<string>` state
- Compute visible graph: large → aggregate → mixed graph → layout → React Flow
- Small → skip aggregation → layout → React Flow directly
- FolderNode click → toggle expand; ModelNode/SourceNode click → navigate
- Preserve all existing filters applied before aggregation
- "Collapse All Folders" button

### Phase 5: Highlighting & Interactions
**Modify:** `LineageFlow.tsx`, node components

- Hover highlighting via `onNodeMouseEnter`/`onNodeMouseLeave` + `getFullChain()`
- `fitView()` replaces manual fit button
- Built-in `<Controls />` replaces custom zoom buttons
- Built-in `<MiniMap />` with node color callback
- Search auto-expands target folder + `fitView({ nodes: [matchId] })`

### Phase 6: Swap & Cleanup
- Replace `<LineageGraph>` with `<LineageFlow>` in LineagePage and ModelPage
- Delete old files: `LineageGraph.tsx`, `useLineage.ts`
- Update E2E tests for new DOM structure

### Phase 7: Polish
- Edge thickness proportional to weight on meta-edges
- Folder hover tooltip
- Performance profiling with large projects
- Simplify node styling for large visible counts

## Suggested Implementation Order

Phases 1→2→5→6 = feature parity with better renderer (no folder aggregation yet).
Then 3→4→7 = scalability layer for large projects.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dagre re-layout on expand (200+ nodes) | MEDIUM | Memoize; WebWorker if >500ms |
| React Flow re-render perf | MEDIUM | React.memo all custom nodes |
| Bundle size (~150KB) | LOW | Acceptable for feature quality |
| E2E test breakage | LOW | Update selectors in Phase 6 |
| Mixed-level edge computation | MEDIUM | Unit tests for buildMixedGraph |

## What We Gain

| Feature | Current (Custom SVG) | React Flow |
|---------|---------------------|------------|
| Pan/Zoom | Manual, can drift | Smooth, touch support |
| MiniMap | Custom implementation | Built-in plugin |
| Zoom Controls | Custom buttons | Built-in `<Controls />` |
| Fit to View | Manual calculation | `fitView()` API |
| Accessibility | None | Keyboard nav, ARIA |
| Mobile/Touch | Not supported | Built-in |
| Custom nodes | SVG elements | React components |
| Extensibility | Build custom | Plugin ecosystem |
