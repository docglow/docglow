import { useMemo } from 'react'
import dagre from 'dagre'
import type { LineageNode, LineageEdge } from '../types'

export interface LayoutNode {
  id: string
  name: string
  resource_type: string
  materialization: string
  test_status: string
  has_description: boolean
  tags: string[]
  x: number
  y: number
  width: number
  height: number
}

export interface LayoutEdge {
  source: string
  target: string
  points: { x: number; y: number }[]
}

export interface DagLayout {
  nodes: LayoutNode[]
  edges: LayoutEdge[]
  width: number
  height: number
}

const NODE_WIDTH = 180
const NODE_HEIGHT = 44

export function useLineageLayout(
  nodes: LineageNode[],
  edges: LineageEdge[],
): DagLayout {
  return useMemo(() => {
    if (nodes.length === 0) {
      return { nodes: [], edges: [], width: 0, height: 0 }
    }

    const g = new dagre.graphlib.Graph()
    g.setGraph({
      rankdir: 'LR',
      nodesep: 20,
      ranksep: 60,
      marginx: 20,
      marginy: 20,
    })
    g.setDefaultEdgeLabel(() => ({}))

    for (const node of nodes) {
      g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
    }

    for (const edge of edges) {
      if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
        g.setEdge(edge.source, edge.target)
      }
    }

    dagre.layout(g)

    const layoutNodes: LayoutNode[] = nodes.map((node) => {
      const pos = g.node(node.id)
      return {
        ...node,
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      }
    })

    const layoutEdges: LayoutEdge[] = edges
      .filter((e) => g.hasNode(e.source) && g.hasNode(e.target))
      .map((edge) => {
        const edgeData = g.edge(edge.source, edge.target)
        return {
          source: edge.source,
          target: edge.target,
          points: edgeData?.points ?? [],
        }
      })

    const graphData = g.graph()

    return {
      nodes: layoutNodes,
      edges: layoutEdges,
      width: (graphData.width ?? 800) + 40,
      height: (graphData.height ?? 400) + 40,
    }
  }, [nodes, edges])
}
