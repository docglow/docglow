import type { DocglowData } from '../types'

export function buildModelColumnsMap(data: DocglowData): Record<string, string[]> {
  const map: Record<string, string[]> = {}
  for (const [id, model] of Object.entries(data.models)) {
    map[id] = model.columns.map(c => c.name)
  }
  for (const [id, source] of Object.entries(data.sources)) {
    map[id] = source.columns.map(c => c.name)
  }
  return map
}
