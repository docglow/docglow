# Plan: Scalable Lineage with Folder-Level Overview + Drill-Down (Dagre + SVG)

> Preserved as Option A. See also: plan-lineage-react-flow.md for the React Flow approach.

## Requirements

The lineage page must handle graphs with 3,000+ nodes (1,587 models + 1,504 sources in point_analytics) while supporting both **architectural overview** and **impact analysis**. The solution is a **folder-level DAG** as the default view for large projects, where folders are collapsed super-nodes that can be expanded inline to reveal individual models. Small projects (< ~100 nodes) keep the existing flat graph.

## Architecture

Two-tier rendering with a single data transformation layer:

```
Raw lineage data (3,000 nodes)
        │
   ┌────▼─────────────────┐
   │ aggregateByFolder()   │  ← New utility
   │ Groups nodes by folder│
   │ Computes meta-edges   │
   └────┬─────────────────┘
        │
   ┌────▼─────────────────┐
   │ Expand/collapse state │  ← Per-folder toggle
   │ Merges expanded       │
   │ folders back into     │
   │ the mixed-level graph │
   └────┬─────────────────┘
        │
   ┌────▼─────────────────┐
   │ Existing LineageGraph │  ← Mostly unchanged
   │ (Dagre + SVG)         │
   └──────────────────────┘
```

Key insight: we don't replace the rendering layer. We add a data transformation step that produces a smaller graph (folder super-nodes + expanded individual nodes), which feeds into the existing LineageGraph component with minimal changes.

## Implementation Phases

### Phase 1: Folder Aggregation Utility
**New file:** `frontend/src/utils/lineageAggregation.ts`

- `aggregateByFolder(nodes, edges)` → `{ folderNodes, folderEdges }`
  - Groups `LineageNode[]` by `folder` property
  - Creates `FolderNode` type (id, folder name, node count, resource types breakdown)
  - Computes meta-edges: if any model in folder A depends on any model in folder B, create one edge A→B with a `weight` (count of individual cross-folder edges)
  - Sources grouped by `source_name`

- `buildMixedGraph(folderNodes, folderEdges, expandedFolders, originalNodes, originalEdges)`
  - Takes the set of currently expanded folder IDs
  - For expanded folders: replaces the super-node with individual models
  - For collapsed folders: keeps the super-node
  - Recomputes edges accordingly

- `shouldUseFolderView(nodes)` → `boolean`
  - Returns `true` when `nodes.length > FOLDER_VIEW_THRESHOLD` (e.g., 100)

### Phase 2: Folder Super-Node Rendering
**Modify:** `LineageGraph.tsx`

- Add a `nodeType` discriminator: `'model' | 'source' | 'folder'`
- `DagNode` variant for folder nodes (larger, folder icon, count subtitle, expand cue)
- Meta-edges with thickness proportional to weight
- Folder nodes get an `onExpand` callback

### Phase 3: Expand/Collapse State in LineagePage
**Modify:** `LineagePage.tsx`

- `expandedFolders: Set<string>` state
- Compute folder-level graph → apply expand state → pass to LineageGraph
- Click folder node to toggle
- Small projects bypass → existing flat graph

### Phase 4: Enhanced Interactions
- Hover tooltips on folder nodes
- Search auto-expands target folder
- Path expansion (expand all folders in dependency chain)
- Edge weight labels

### Phase 5: Polish & Performance
- Expand/collapse animations
- Memoize folder aggregation
- Viewport culling if needed

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dagre re-layout on expand is slow (200+ visible nodes) | MEDIUM | Memoize; WebWorker if needed |
| Mixed-level edge computation complexity | MEDIUM | Unit tests for buildMixedGraph |
| Filter interaction with folder view | MEDIUM | Apply filters before aggregation |

## Dependencies
- No new libraries (Dagre + SVG)
- React Flow as future upgrade path if perf issues arise
