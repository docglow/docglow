import dagre from 'dagre'
import type { Node, Edge } from '@xyflow/react'
import type { ColumnEdge } from '../types'

export interface TraceNodeData {
  readonly modelId: string
  readonly modelName: string
  readonly resourceType: string
  readonly columns: readonly string[]
  readonly isCurrent: boolean
  readonly currentColumn: string | null
  [key: string]: unknown
}

export interface TraceLayoutResult {
  readonly nodes: Node<TraceNodeData>[]
  readonly edges: Edge[]
}

const NODE_WIDTH = 180
const NODE_BASE_HEIGHT = 44
const COLUMN_ROW_HEIGHT = 22

/** Transformation type → edge color */
const EDGE_COLORS: Record<string, string> = {
  passthrough: '#16a34a',
  derived: '#d97706',
  aggregated: '#7c3aed',
  unknown: '#6b7280',
  direct: '#16a34a',
  rename: '#d97706',
}

/**
 * Convert trace edges into ReactFlow nodes + edges using dagre for LR layout.
 * Groups columns by model, creates one node per model, and one edge per ColumnEdge.
 */
export function buildTraceLayout(
  traceEdges: readonly ColumnEdge[],
  currentModelId: string,
  currentColumn: string,
): TraceLayoutResult {
  if (traceEdges.length === 0) {
    return { nodes: [], edges: [] }
  }

  // Collect all models and their participating columns
  const modelColumns = new Map<string, Set<string>>()

  const addColumn = (modelId: string, column: string) => {
    const existing = modelColumns.get(modelId)
    if (existing) {
      existing.add(column)
    } else {
      modelColumns.set(modelId, new Set([column]))
    }
  }

  // Always include the current column
  addColumn(currentModelId, currentColumn)

  for (const edge of traceEdges) {
    addColumn(edge.sourceModel, edge.sourceColumn)
    addColumn(edge.targetModel, edge.targetColumn)
  }

  // Build dagre graph
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 80 })
  g.setDefaultEdgeLabel(() => ({}))

  // Add nodes
  for (const [modelId, cols] of modelColumns) {
    const height = NODE_BASE_HEIGHT + cols.size * COLUMN_ROW_HEIGHT
    g.setNode(modelId, { width: NODE_WIDTH, height })
  }

  // Add edges (deduplicated by model pair for layout purposes)
  const layoutEdges = new Set<string>()
  for (const edge of traceEdges) {
    const key = `${edge.sourceModel}->${edge.targetModel}`
    if (!layoutEdges.has(key)) {
      layoutEdges.add(key)
      g.setEdge(edge.sourceModel, edge.targetModel)
    }
  }

  dagre.layout(g)

  // Convert to ReactFlow nodes
  const nodes: Node<TraceNodeData>[] = Array.from(modelColumns.entries()).map(
    ([modelId, cols]) => {
      const dagreNode = g.node(modelId)
      const sortedCols = [...cols].sort()
      const resourceType = modelId.split('.')[0] ?? 'model'
      const modelName = modelId.split('.').pop() ?? modelId

      return {
        id: modelId,
        type: 'columnTrace',
        position: {
          x: dagreNode.x - NODE_WIDTH / 2,
          y: dagreNode.y - dagreNode.height / 2,
        },
        data: {
          modelId,
          modelName,
          resourceType,
          columns: sortedCols,
          isCurrent: modelId === currentModelId,
          currentColumn: modelId === currentModelId ? currentColumn : null,
        },
      }
    },
  )

  // Convert to ReactFlow edges (one per ColumnEdge for column-level connections)
  const edges: Edge[] = traceEdges.map((edge, i) => ({
    id: `trace-${i}`,
    source: edge.sourceModel,
    target: edge.targetModel,
    sourceHandle: `col-${edge.sourceColumn}-source`,
    targetHandle: `col-${edge.targetColumn}-target`,
    style: {
      stroke: EDGE_COLORS[edge.transformation] ?? EDGE_COLORS.unknown,
      strokeWidth: 2,
    },
    animated: edge.transformation === 'passthrough' || edge.transformation === 'direct',
  }))

  return { nodes, edges }
}
