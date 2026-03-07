import type { LineageEdge } from '../types'

/** Collect all upstream node IDs (recursive BFS backward). */
export function getUpstream(nodeId: string, edges: LineageEdge[]): Set<string> {
  const visited = new Set<string>()
  const queue = [nodeId]

  while (queue.length > 0) {
    const current = queue.shift()!
    for (const e of edges) {
      if (e.target === current && !visited.has(e.source)) {
        visited.add(e.source)
        queue.push(e.source)
      }
    }
  }

  return visited
}

/** Collect all downstream node IDs (recursive BFS forward). */
export function getDownstream(nodeId: string, edges: LineageEdge[]): Set<string> {
  const visited = new Set<string>()
  const queue = [nodeId]

  while (queue.length > 0) {
    const current = queue.shift()!
    for (const e of edges) {
      if (e.source === current && !visited.has(e.target)) {
        visited.add(e.target)
        queue.push(e.target)
      }
    }
  }

  return visited
}

/** Get full dependency chain: upstream + downstream + self. */
export function getFullChain(nodeId: string, edges: LineageEdge[]): Set<string> {
  const upstream = getUpstream(nodeId, edges)
  const downstream = getDownstream(nodeId, edges)
  return new Set([nodeId, ...upstream, ...downstream])
}

/** Check if an edge connects two nodes in the highlighted set. */
export function isEdgeHighlighted(
  edge: LineageEdge,
  highlightedNodes: Set<string>,
): boolean {
  return highlightedNodes.has(edge.source) && highlightedNodes.has(edge.target)
}
