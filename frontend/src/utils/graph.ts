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

export function getSubgraph(
  nodeId: string,
  nodes: LineageNode[],
  edges: LineageEdge[],
  depth: number = 2,
): { nodes: LineageNode[]; edges: LineageEdge[] } {
  const upstream = getUpstream(nodeId, edges, depth)
  const downstream = getDownstream(nodeId, edges, depth)
  const relevantIds = new Set([nodeId, ...upstream, ...downstream])

  return {
    nodes: nodes.filter((n) => relevantIds.has(n.id)),
    edges: edges.filter((e) => relevantIds.has(e.source) && relevantIds.has(e.target)),
  }
}
