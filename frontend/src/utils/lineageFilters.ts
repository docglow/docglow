import { useState, useCallback } from 'react'
import type { FilterState, FilterMode } from '../components/ui/FilterDropdown'
import type { LineageNode, LineageEdge } from '../types'

export const EMPTY_FILTER: FilterState = { mode: 'include', selected: new Set() }

export const RESOURCE_TYPES = ['model', 'source', 'seed', 'snapshot', 'exposure', 'metric']

export function applyFilters(
  nodes: LineageNode[],
  edges: LineageEdge[],
  typeFilter: FilterState,
  tagFilter: FilterState,
  folderFilter: FilterState,
  layerFilter: FilterState = EMPTY_FILTER,
): { nodes: LineageNode[]; edges: LineageEdge[] } {
  let filtered = nodes

  if (typeFilter.selected.size > 0) {
    if (typeFilter.mode === 'include') {
      filtered = filtered.filter(n => typeFilter.selected.has(n.resource_type))
    } else {
      filtered = filtered.filter(n => !typeFilter.selected.has(n.resource_type))
    }
  }

  if (tagFilter.selected.size > 0) {
    if (tagFilter.mode === 'include') {
      filtered = filtered.filter(n => n.tags.some(t => tagFilter.selected.has(t)))
    } else {
      filtered = filtered.filter(n => !n.tags.some(t => tagFilter.selected.has(t)))
    }
  }

  if (folderFilter.selected.size > 0) {
    if (folderFilter.mode === 'include') {
      filtered = filtered.filter(n => folderFilter.selected.has(n.folder))
    } else {
      filtered = filtered.filter(n => !folderFilter.selected.has(n.folder))
    }
  }

  if (layerFilter.selected.size > 0) {
    if (layerFilter.mode === 'include') {
      // Include: only nodes whose layer is in the set. Nodes with no layer are excluded.
      filtered = filtered.filter(n => n.layer != null && layerFilter.selected.has(String(n.layer)))
    } else {
      // Exclude: drop nodes whose layer is in the set. Nodes with no layer survive.
      filtered = filtered.filter(n => n.layer == null || !layerFilter.selected.has(String(n.layer)))
    }
  }

  const nodeIds = new Set(filtered.map(n => n.id))
  const filteredEdges = edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

  return { nodes: filtered, edges: filteredEdges }
}

export function useFilterState(): [FilterState, (value: string) => void, (mode: FilterMode) => void, () => void] {
  const [state, setState] = useState<FilterState>(EMPTY_FILTER)

  const toggle = useCallback((value: string) => {
    setState(prev => {
      const next = new Set(prev.selected)
      if (next.has(value)) next.delete(value)
      else next.add(value)
      return { ...prev, selected: next }
    })
  }, [])

  const setMode = useCallback((mode: FilterMode) => {
    setState(prev => ({ ...prev, mode }))
  }, [])

  const clear = useCallback(() => {
    setState(EMPTY_FILTER)
  }, [])

  return [state, toggle, setMode, clear]
}

export function computeSubgraphOptions(nodes: LineageNode[]) {
  const tags = new Set<string>()
  const folders = new Set<string>()
  const types = new Set<string>()
  const layers = new Set<string>()
  for (const n of nodes) {
    for (const t of n.tags) tags.add(t)
    if (n.folder) folders.add(n.folder)
    types.add(n.resource_type)
    if (n.layer != null) layers.add(String(n.layer))
  }
  return {
    tags: [...tags].sort(),
    folders: [...folders].sort(),
    types: [...types].sort(),
    layers: [...layers].sort((a, b) => Number(a) - Number(b)),
  }
}
