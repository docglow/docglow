import { create } from 'zustand'

interface ColumnSelection {
  modelId: string
  columnName: string
}

interface ColumnHighlightState {
  selectedColumn: ColumnSelection | null
  expandedNodeIds: Set<string>
  selectColumn: (modelId: string, columnName: string) => void
  clearSelection: () => void
  toggleNodeExpanded: (nodeId: string) => void
}

export const useColumnHighlightStore = create<ColumnHighlightState>((set, get) => ({
  selectedColumn: null,
  expandedNodeIds: new Set(),

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
    const { expandedNodeIds, selectedColumn } = get()
    const next = new Set(expandedNodeIds)
    if (next.has(nodeId)) {
      next.delete(nodeId)
      // Clear selection if the collapsing node contains the selected column
      if (selectedColumn?.modelId === nodeId) {
        set({ expandedNodeIds: next, selectedColumn: null })
        return
      }
    } else {
      next.add(nodeId)
    }
    set({ expandedNodeIds: next })
  },

}))
