import type { LineageEdge } from '../types'

/** Build adjacency index for fast traversal (avoids scanning all edges per BFS step). */
function buildAdjacency(edges: LineageEdge[]): {
  byTarget: Map<string, string[]>
  bySource: Map<string, string[]>
} {
  const byTarget = new Map<string, string[]>()
  const bySource = new Map<string, string[]>()
  for (const e of edges) {
    const t = byTarget.get(e.target)
    if (t) t.push(e.source)
    else byTarget.set(e.target, [e.source])
    const s = bySource.get(e.source)
    if (s) s.push(e.target)
    else bySource.set(e.source, [e.target])
  }
  return { byTarget, bySource }
}

/** Collect upstream node IDs via BFS. Optional maxDepth caps traversal depth. */
export function getUpstream(nodeId: string, edges: LineageEdge[], maxDepth?: number): Set<string> {
  const { byTarget } = buildAdjacency(edges)
  const visited = new Set<string>()
  let frontier = [nodeId]
  let depth = 0

  while (frontier.length > 0 && (maxDepth == null || depth < maxDepth)) {
    const next: string[] = []
    for (const current of frontier) {
      for (const source of (byTarget.get(current) ?? [])) {
        if (!visited.has(source)) {
          visited.add(source)
          next.push(source)
        }
      }
    }
    frontier = next
    depth++
  }

  return visited
}

/** Collect downstream node IDs via BFS. Optional maxDepth caps traversal depth. */
export function getDownstream(nodeId: string, edges: LineageEdge[], maxDepth?: number): Set<string> {
  const { bySource } = buildAdjacency(edges)
  const visited = new Set<string>()
  let frontier = [nodeId]
  let depth = 0

  while (frontier.length > 0 && (maxDepth == null || depth < maxDepth)) {
    const next: string[] = []
    for (const current of frontier) {
      for (const target of (bySource.get(current) ?? [])) {
        if (!visited.has(target)) {
          visited.add(target)
          next.push(target)
        }
      }
    }
    frontier = next
    depth++
  }

  return visited
}

/** Get dependency chain: upstream + downstream + self, capped to maxDepth per direction. */
export function getFullChain(nodeId: string, edges: LineageEdge[], maxDepth?: number): Set<string> {
  const upstream = getUpstream(nodeId, edges, maxDepth)
  const downstream = getDownstream(nodeId, edges, maxDepth)
  return new Set([nodeId, ...upstream, ...downstream])
}

/** Get union of dependency chains for multiple nodes. */
export function getUnionChain(
  nodeIds: string[],
  edges: LineageEdge[],
  maxDepth?: number,
): Set<string> {
  if (nodeIds.length === 0) return new Set()
  if (nodeIds.length === 1) return getFullChain(nodeIds[0], edges, maxDepth)

  const result = new Set<string>()
  for (const nodeId of nodeIds) {
    for (const id of getFullChain(nodeId, edges, maxDepth)) {
      result.add(id)
    }
  }
  return result
}

/** Check if an edge connects two nodes in the highlighted set. */
export function isEdgeHighlighted(
  edge: LineageEdge,
  highlightedNodes: Set<string>,
): boolean {
  return highlightedNodes.has(edge.source) && highlightedNodes.has(edge.target)
}
