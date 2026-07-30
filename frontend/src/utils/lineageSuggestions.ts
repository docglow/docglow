/**
 * Entry points into a cold graph, ranked by connectivity.
 *
 * A DAG with no node selected is a hairball; the most-connected models are the
 * ones worth landing on first. Shared by the Lineage Explorer and the Overview
 * so both offer the same starting points.
 */
import type { LineageEdge, LineageNode } from '../types'

export interface ModelSuggestion {
  readonly node: LineageNode
  readonly upstreamCount: number
  readonly downstreamCount: number
  readonly totalConnections: number
}

export function computeSuggestions(
  nodes: readonly LineageNode[],
  edges: readonly LineageEdge[],
  limit = 12,
): ModelSuggestion[] {
  const inDegree = new Map<string, number>()
  const outDegree = new Map<string, number>()
  for (const e of edges) {
    outDegree.set(e.source, (outDegree.get(e.source) ?? 0) + 1)
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
  }

  return nodes
    .filter(n => n.resource_type === 'model')
    .map(n => ({
      node: n,
      upstreamCount: inDegree.get(n.id) ?? 0,
      downstreamCount: outDegree.get(n.id) ?? 0,
      totalConnections: (inDegree.get(n.id) ?? 0) + (outDegree.get(n.id) ?? 0),
    }))
    .sort((a, b) => b.totalConnections - a.totalConnections || a.node.name.localeCompare(b.node.name))
    .slice(0, limit)
}
