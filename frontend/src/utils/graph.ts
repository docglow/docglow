import type { LineageEdge, LineageNode } from '../types'

export function getUpstream(
  nodeId: string,
  edges: LineageEdge[],
  depth: number = 2,
): Set<string> {
  const result = new Set<string>()
  let current = new Set([nodeId])

  for (let i = 0; i < depth; i++) {
    const next = new Set<string>()
    for (const edge of edges) {
      if (current.has(edge.target) && !result.has(edge.source)) {
        next.add(edge.source)
        result.add(edge.source)
      }
    }
    if (next.size === 0) break
    current = next
  }

  return result
}

export function getDownstream(
  nodeId: string,
  edges: LineageEdge[],
  depth: number = 2,
): Set<string> {
  const result = new Set<string>()
  let current = new Set([nodeId])

  for (let i = 0; i < depth; i++) {
    const next = new Set<string>()
    for (const edge of edges) {
      if (current.has(edge.source) && !result.has(edge.target)) {
        next.add(edge.target)
        result.add(edge.target)
      }
    }
    if (next.size === 0) break
    current = next
  }

  return result
}

export type LineageDirection = 'both' | 'upstream' | 'downstream'

export function getSubgraph(
  nodeId: string,
  nodes: LineageNode[],
  edges: LineageEdge[],
  depth: number = 2,
  direction: LineageDirection = 'both',
): { nodes: LineageNode[]; edges: LineageEdge[] } {
  const upstream = direction !== 'downstream' ? getUpstream(nodeId, edges, depth) : new Set<string>()
  const downstream = direction !== 'upstream' ? getDownstream(nodeId, edges, depth) : new Set<string>()
  const relevantIds = new Set([nodeId, ...upstream, ...downstream])

  return {
    nodes: nodes.filter((n) => relevantIds.has(n.id)),
    edges: edges.filter((e) => relevantIds.has(e.source) && relevantIds.has(e.target)),
  }
}

/** Compute the union of subgraphs for multiple pinned nodes. */
export function getUnionSubgraph(
  nodeIds: string[],
  nodes: LineageNode[],
  edges: LineageEdge[],
  depth: number = 2,
  direction: LineageDirection = 'both',
): { nodes: LineageNode[]; edges: LineageEdge[] } {
  if (nodeIds.length === 0) return { nodes: [], edges: [] }
  if (nodeIds.length === 1) return getSubgraph(nodeIds[0], nodes, edges, depth, direction)

  const relevantIds = new Set<string>()
  for (const nodeId of nodeIds) {
    relevantIds.add(nodeId)
    const upstream = direction !== 'downstream' ? getUpstream(nodeId, edges, depth) : new Set<string>()
    const downstream = direction !== 'upstream' ? getDownstream(nodeId, edges, depth) : new Set<string>()
    for (const id of upstream) relevantIds.add(id)
    for (const id of downstream) relevantIds.add(id)
  }

  return {
    nodes: nodes.filter((n) => relevantIds.has(n.id)),
    edges: edges.filter((e) => relevantIds.has(e.source) && relevantIds.has(e.target)),
  }
}
