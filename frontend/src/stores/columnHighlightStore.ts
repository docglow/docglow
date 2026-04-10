import { create } from 'zustand'

interface ColumnSelection {
  modelId: string
  columnName: string
}

interface ColumnHighlightState {
  selectedColumn: ColumnSelection | null
  expandedNodeIds: Set<string>
  autoExpandedNodeIds: Set<string>
  manuallyCollapsedIds: Set<string>
  selectColumn: (modelId: string, columnName: string) => void
  clearSelection: () => void
  toggleNodeExpanded: (nodeId: string) => void
  setAutoExpandedNodes: (nodeIds: Set<string>) => void
  isNodeExpanded: (nodeId: string) => boolean
}

export const useColumnHighlightStore = create<ColumnHighlightState>((set, get) => ({
  selectedColumn: null,
  expandedNodeIds: new Set(),
  autoExpandedNodeIds: new Set(),
  manuallyCollapsedIds: new Set(),

  selectColumn: (modelId, columnName) => {
    const current = get().selectedColumn
    if (current?.modelId === modelId && current?.columnName === columnName) {
      set({ selectedColumn: null })
    } else {
      set({ selectedColumn: { modelId, columnName } })
    }
  },

  clearSelection: () => {
    set({ selectedColumn: null })
  },

  toggleNodeExpanded: (nodeId) => {
    const { expandedNodeIds, autoExpandedNodeIds, manuallyCollapsedIds, selectedColumn } = get()

    // If this node was auto-expanded and not manually collapsed, collapse it
    if (autoExpandedNodeIds.has(nodeId) && !manuallyCollapsedIds.has(nodeId)) {
      const nextCollapsed = new Set(manuallyCollapsedIds)
      nextCollapsed.add(nodeId)
      if (selectedColumn?.modelId === nodeId) {
        set({ manuallyCollapsedIds: nextCollapsed, selectedColumn: null })
      } else {
        set({ manuallyCollapsedIds: nextCollapsed })
      }
      return
    }

    // If this node was manually collapsed after auto-expand, re-expand it
    if (autoExpandedNodeIds.has(nodeId) && manuallyCollapsedIds.has(nodeId)) {
      const nextCollapsed = new Set(manuallyCollapsedIds)
      nextCollapsed.delete(nodeId)
      set({ manuallyCollapsedIds: nextCollapsed })
      return
    }

    // Normal manual toggle
    const next = new Set(expandedNodeIds)
    if (next.has(nodeId)) {
      next.delete(nodeId)
      if (selectedColumn?.modelId === nodeId) {
        set({ expandedNodeIds: next, selectedColumn: null })
        return
      }
    } else {
      next.add(nodeId)
    }
    set({ expandedNodeIds: next })
  },

  setAutoExpandedNodes: (nodeIds) => {
    set({ autoExpandedNodeIds: nodeIds, manuallyCollapsedIds: new Set() })
  },

  isNodeExpanded: (nodeId) => {
    const { expandedNodeIds, autoExpandedNodeIds, manuallyCollapsedIds } = get()
    if (expandedNodeIds.has(nodeId)) return true
    if (autoExpandedNodeIds.has(nodeId) && !manuallyCollapsedIds.has(nodeId)) return true
    return false
  },
}))
