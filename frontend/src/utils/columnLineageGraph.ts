import type { ColumnLineageData, ColumnEdge, ColumnDownstreamDependency } from '../types'

const MAX_TRACE_DEPTH = 6

interface ColumnRef {
  modelId: string
  columnName: string
}

interface TraceResult {
  edges: ColumnEdge[]
  /** Map of modelId -> Set of column names that participate in the trace */
  highlightedColumns: Map<string, Set<string>>
}

/**
 * Build a reverse index: for each (sourceModel, sourceColumn), find all
 * (targetModel, targetColumn) that reference it. Used for downstream tracing.
 */
export function buildReverseIndex(
  columnLineage: ColumnLineageData
): Map<string, ColumnRef[]> {
  const index = new Map<string, ColumnRef[]>()
  for (const [targetModel, columns] of Object.entries(columnLineage)) {
    for (const [targetColumn, deps] of Object.entries(columns)) {
      for (const dep of deps) {
        const key = `${dep.source_model}::${dep.source_column.toLowerCase()}`
        const refs = index.get(key) ?? []
        refs.push({ modelId: targetModel, columnName: targetColumn })
        index.set(key, refs)
      }
    }
  }
  return index
}

/**
 * Trace upstream columns: follow column_lineage[modelId][columnName] entries recursively.
 */
export function traceColumnUpstream(
  modelId: string,
  columnName: string,
  columnLineage: ColumnLineageData,
  maxDepth: number = MAX_TRACE_DEPTH,
): ColumnEdge[] {
  const edges: ColumnEdge[] = []
  const visited = new Set<string>()
  const queue: Array<{ model: string; column: string; depth: number }> = [
    { model: modelId, column: columnName, depth: 0 },
  ]

  while (queue.length > 0) {
    const { model, column, depth } = queue.shift()!
    if (depth >= maxDepth) continue

    const deps = columnLineage[model]?.[column]
    if (!deps) continue

    for (const dep of deps) {
      const edgeKey = `${dep.source_model}::${dep.source_column}::${model}::${column}`
      if (visited.has(edgeKey)) continue
      visited.add(edgeKey)

      edges.push({
        sourceModel: dep.source_model,
        sourceColumn: dep.source_column,
        targetModel: model,
        targetColumn: column,
        transformation: dep.transformation,
      })

      queue.push({ model: dep.source_model, column: dep.source_column, depth: depth + 1 })
    }
  }

  return edges
}

/**
 * Trace downstream columns: find all models that reference (modelId, columnName)
 * as a source, then recurse.
 */
export function traceColumnDownstream(
  modelId: string,
  columnName: string,
  columnLineage: ColumnLineageData,
  reverseIndex: Map<string, ColumnRef[]>,
  maxDepth: number = MAX_TRACE_DEPTH,
): ColumnEdge[] {
  const edges: ColumnEdge[] = []
  const visited = new Set<string>()
  const queue: Array<{ model: string; column: string; depth: number }> = [
    { model: modelId, column: columnName, depth: 0 },
  ]

  while (queue.length > 0) {
    const { model, column, depth } = queue.shift()!
    if (depth >= maxDepth) continue

    const key = `${model}::${column.toLowerCase()}`
    const consumers = reverseIndex.get(key)
    if (!consumers) continue

    for (const consumer of consumers) {
      const dep = columnLineage[consumer.modelId]?.[consumer.columnName]?.find(
        d => d.source_model === model && d.source_column.toLowerCase() === column.toLowerCase()
      )
      const edgeKey = `${model}::${column}::${consumer.modelId}::${consumer.columnName}`
      if (visited.has(edgeKey)) continue
      visited.add(edgeKey)

      edges.push({
        sourceModel: model,
        sourceColumn: column,
        targetModel: consumer.modelId,
        targetColumn: consumer.columnName,
        transformation: dep?.transformation ?? 'derived',
      })

      queue.push({ model: consumer.modelId, column: consumer.columnName, depth: depth + 1 })
    }
  }

  return edges
}

/**
 * Get the full column trace result: upstream + downstream edges and all highlighted columns.
 */
export function getColumnTraceResult(
  modelId: string,
  columnName: string,
  columnLineage: ColumnLineageData,
  reverseIndex: Map<string, ColumnRef[]>,
  maxDepth: number = MAX_TRACE_DEPTH,
): TraceResult {
  const upstreamEdges = traceColumnUpstream(modelId, columnName, columnLineage, maxDepth)
  const downstreamEdges = traceColumnDownstream(modelId, columnName, columnLineage, reverseIndex, maxDepth)

  const allEdges = [...upstreamEdges, ...downstreamEdges]

  // Build highlighted columns map
  const highlightedColumns = new Map<string, Set<string>>()

  const addHighlight = (model: string, column: string) => {
    const existing = highlightedColumns.get(model)
    if (existing) {
      existing.add(column)
    } else {
      highlightedColumns.set(model, new Set([column]))
    }
  }

  // The selected column itself
  addHighlight(modelId, columnName)

  // All columns referenced in edges
  for (const edge of allEdges) {
    addHighlight(edge.sourceModel, edge.sourceColumn)
    addHighlight(edge.targetModel, edge.targetColumn)
  }

  return { edges: allEdges, highlightedColumns }
}

/**
 * Build a map of column_name -> downstream consumers for a specific model.
 * Used by ColumnTable to show which models consume each column.
 */
export function buildDownstreamMap(
  modelId: string,
  columnLineage: ColumnLineageData,
): Record<string, ColumnDownstreamDependency[]> {
  const result: Record<string, ColumnDownstreamDependency[]> = {}

  // Scan all models' lineage to find references to columns from modelId
  for (const [targetModelId, columns] of Object.entries(columnLineage)) {
    if (targetModelId === modelId) continue

    for (const [targetColumn, deps] of Object.entries(columns)) {
      for (const dep of deps) {
        if (dep.source_model !== modelId) continue

        const sourceCol = dep.source_column
        const existing = result[sourceCol] ?? []
        existing.push({
          target_model: targetModelId,
          target_column: targetColumn,
          transformation: dep.transformation,
        })
        result[sourceCol] = existing
      }
    }
  }

  return result
}
