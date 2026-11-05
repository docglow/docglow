import type { DocglowData } from '../types'

export function buildModelColumnsMap(data: DocglowData): Record<string, string[]> {
  const map: Record<string, string[]> = {}
  for (const [id, model] of Object.entries(data.models)) {
    map[id] = model.columns.map(c => c.name)
  }
  for (const [id, source] of Object.entries(data.sources)) {
    map[id] = source.columns.map(c => c.name)
  }
  // A metric is a one-column node in column lineage, the column being the
  // metric itself, so it can be expanded in the lineage graph like a model.
  for (const [id, metric] of Object.entries(data.metrics)) {
    if (data.column_lineage?.[id]) map[id] = [metric.name]
  }
  return map
}
