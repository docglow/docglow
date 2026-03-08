import { useState, useMemo, useCallback } from 'react'
import { useProjectStore } from '../stores/projectStore'
import { LineageFlow } from '../components/lineage/LineageFlow'
import { FilterDropdown, type FilterState, type FilterMode } from '../components/ui/FilterDropdown'
import { getSubgraph } from '../utils/graph'
import type { LineageNode, LineageEdge } from '../types'

interface ModelSuggestion {
  node: LineageNode
  upstreamCount: number
  downstreamCount: number
  totalConnections: number
}

function computeSuggestions(nodes: LineageNode[], edges: LineageEdge[]): ModelSuggestion[] {
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
    .sort((a, b) => b.totalConnections - a.totalConnections)
    .slice(0, 12)
}

const EMPTY_FILTER: FilterState = { mode: 'include', selected: new Set() }

const RESOURCE_TYPES = ['model', 'source', 'seed', 'snapshot', 'exposure', 'metric']

function applyFilters(
  nodes: LineageNode[],
  edges: LineageEdge[],
  typeFilter: FilterState,
  tagFilter: FilterState,
  folderFilter: FilterState,
): { nodes: LineageNode[]; edges: LineageEdge[] } {
  let filtered = nodes

  // Type filter
  if (typeFilter.selected.size > 0) {
    if (typeFilter.mode === 'include') {
      filtered = filtered.filter(n => typeFilter.selected.has(n.resource_type))
    } else {
      filtered = filtered.filter(n => !typeFilter.selected.has(n.resource_type))
    }
  }

  // Tag filter
  if (tagFilter.selected.size > 0) {
    if (tagFilter.mode === 'include') {
      filtered = filtered.filter(n => n.tags.some(t => tagFilter.selected.has(t)))
    } else {
      filtered = filtered.filter(n => !n.tags.some(t => tagFilter.selected.has(t)))
    }
  }

  // Folder filter
  if (folderFilter.selected.size > 0) {
    if (folderFilter.mode === 'include') {
      filtered = filtered.filter(n => folderFilter.selected.has(n.folder))
    } else {
      filtered = filtered.filter(n => !folderFilter.selected.has(n.folder))
    }
  }

  const nodeIds = new Set(filtered.map(n => n.id))
  const filteredEdges = edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

  return { nodes: filtered, edges: filteredEdges }
}

function useFilterState(): [FilterState, (value: string) => void, (mode: FilterMode) => void, () => void] {
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

export function LineagePage() {
  const { data } = useProjectStore()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [depth, setDepth] = useState(2)
  const [search, setSearch] = useState('')

  const [typeFilter, toggleType, setTypeMode, clearTypes] = useFilterState()
  const [tagFilter, toggleTag, setTagMode, clearTags] = useFilterState()
  const [folderFilter, toggleFolder, setFolderMode, clearFolders] = useFilterState()

  const suggestions = useMemo(() => {
    if (!data) return []
    return computeSuggestions(data.lineage.nodes, data.lineage.edges)
  }, [data])

  const searchResults = useMemo(() => {
    if (!data || !search) return []
    const q = search.toLowerCase()
    return data.lineage.nodes
      .filter(n =>
        n.resource_type === 'model' &&
        (n.name.toLowerCase().includes(q) || n.folder.toLowerCase().includes(q))
      )
      .slice(0, 20)
  }, [data, search])

  // Compute subgraph, then apply filters
  const subgraph = useMemo(() => {
    if (!data || !selectedNodeId) return null
    const raw = getSubgraph(selectedNodeId, data.lineage.nodes, data.lineage.edges, depth)
    return applyFilters(raw.nodes, raw.edges, typeFilter, tagFilter, folderFilter)
  }, [data, selectedNodeId, depth, typeFilter, tagFilter, folderFilter])

  // Available options derived from the unfiltered subgraph
  const subgraphOptions = useMemo(() => {
    if (!data || !selectedNodeId) return { tags: [], folders: [], types: RESOURCE_TYPES }
    const raw = getSubgraph(selectedNodeId, data.lineage.nodes, data.lineage.edges, depth)
    const tags = new Set<string>()
    const folders = new Set<string>()
    const types = new Set<string>()
    for (const n of raw.nodes) {
      for (const t of n.tags) tags.add(t)
      if (n.folder) folders.add(n.folder)
      types.add(n.resource_type)
    }
    return {
      tags: [...tags].sort(),
      folders: [...folders].sort(),
      types: [...types].sort(),
    }
  }, [data, selectedNodeId, depth])

  const selectedNode = useMemo(() => {
    if (!data || !selectedNodeId) return null
    return data.lineage.nodes.find(n => n.id === selectedNodeId) ?? null
  }, [data, selectedNodeId])

  const handleSelectModel = useCallback((id: string) => {
    setSelectedNodeId(id)
    setSearch('')
  }, [])

  const handleClearSelection = useCallback(() => {
    setSelectedNodeId(null)
    setSearch('')
    clearTypes()
    clearTags()
    clearFolders()
  }, [clearTypes, clearTags, clearFolders])

  const hasActiveFilters = typeFilter.selected.size > 0 || tagFilter.selected.size > 0 || folderFilter.selected.size > 0

  const clearAllFilters = useCallback(() => {
    clearTypes()
    clearTags()
    clearFolders()
  }, [clearTypes, clearTags, clearFolders])

  if (!data) return null

  // Exploring a model's lineage
  if (selectedNodeId && subgraph) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center gap-3 mb-2 shrink-0 flex-wrap">
          <button
            onClick={handleClearSelection}
            className="p-1 rounded hover:bg-[var(--bg-surface)] cursor-pointer transition-colors text-[var(--text-muted)]"
            title="Back to overview"
          >
            <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="mr-2">
            <h1 className="text-lg font-bold leading-tight">{selectedNode?.name ?? selectedNodeId}</h1>
            <span className="text-xs text-[var(--text-muted)]">{selectedNode?.folder}</span>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-[var(--text-muted)]">Depth</label>
            <input
              type="range"
              min={1}
              max={6}
              value={depth}
              onChange={e => setDepth(Number(e.target.value))}
              className="w-20 accent-[var(--primary)]"
            />
            <span className="text-xs font-medium w-4 text-center">{depth}</span>
          </div>

          <div className="h-4 w-px bg-[var(--border)]" />

          <FilterDropdown
            label="Types"
            options={subgraphOptions.types}
            filter={typeFilter}
            onToggle={toggleType}
            onSetMode={setTypeMode}
            onClear={clearTypes}
          />
          {subgraphOptions.tags.length > 0 && (
            <FilterDropdown
              label="Tags"
              options={subgraphOptions.tags}
              filter={tagFilter}
              onToggle={toggleTag}
              onSetMode={setTagMode}
              onClear={clearTags}
            />
          )}
          {subgraphOptions.folders.length > 0 && (
            <FilterDropdown
              label="Folders"
              options={subgraphOptions.folders}
              filter={folderFilter}
              onToggle={toggleFolder}
              onSetMode={setFolderMode}
              onClear={clearFolders}
              displayLabel={(v) => v.split('/').pop() ?? v}
            />
          )}

          {hasActiveFilters && (
            <button
              onClick={clearAllFilters}
              className="px-2 py-1 text-xs rounded bg-danger/10 text-danger hover:bg-danger/20 cursor-pointer transition-colors"
            >
              Clear filters
            </button>
          )}

          <span className="text-xs text-[var(--text-muted)] ml-auto">
            {subgraph.nodes.length} nodes · {subgraph.edges.length} edges
          </span>
        </div>

        <div className="flex-1 relative min-h-0">
          <LineageFlow
            nodes={subgraph.nodes}
            edges={subgraph.edges}
            highlightId={selectedNodeId}
          />
        </div>
      </div>
    )
  }

  // Landing: model picker
  const showSearchResults = search.length > 0

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto py-8 px-4">
          <h1 className="text-2xl font-bold mb-1">Lineage Explorer</h1>
          <p className="text-sm text-[var(--text-muted)] mb-6">
            Select a model to explore its upstream and downstream dependencies.
          </p>

          {/* Search */}
          <div className="relative mb-8">
            <div className="flex items-center gap-2 px-3 py-2.5 border border-[var(--border)] rounded-lg bg-[var(--bg)] focus-within:border-primary transition-colors">
              <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="var(--text-muted, #64748b)" strokeWidth={2}>
                <circle cx={11} cy={11} r={8} />
                <path d="m21 21-4.35-4.35" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search for a model..."
                className="flex-1 bg-transparent outline-none text-sm"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="text-[var(--text-muted)] hover:text-[var(--text)] cursor-pointer"
                >
                  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            {showSearchResults && (
              <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-[var(--bg)] border border-[var(--border)] rounded-lg shadow-lg max-h-64 overflow-y-auto">
                {searchResults.length === 0 ? (
                  <div className="px-4 py-3 text-sm text-[var(--text-muted)]">No models found</div>
                ) : (
                  searchResults.map(node => (
                    <button
                      key={node.id}
                      onClick={() => handleSelectModel(node.id)}
                      className="w-full text-left px-4 py-2 text-sm hover:bg-[var(--bg-surface)]
                                 cursor-pointer transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="font-medium text-[var(--text)]">{node.name}</div>
                        <div className="text-xs text-[var(--text-muted)]">{node.folder}</div>
                      </div>
                      <span className="text-xs text-[var(--text-muted)] shrink-0 ml-2">
                        {node.materialization}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Suggestions */}
          {!showSearchResults && (
            <>
              <h2 className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                Suggested starting points
              </h2>
              <p className="text-xs text-[var(--text-muted)] mb-4">
                Models with the most connections in your project — good places to start exploring.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {suggestions.map(s => (
                  <button
                    key={s.node.id}
                    onClick={() => handleSelectModel(s.node.id)}
                    className="text-left p-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]
                               hover:border-primary/50 cursor-pointer transition-colors group"
                  >
                    <div className="font-medium text-sm text-[var(--text)] group-hover:text-primary transition-colors truncate">
                      {s.node.name}
                    </div>
                    <div className="text-xs text-[var(--text-muted)] truncate mt-0.5">
                      {s.node.folder}
                    </div>
                    <div className="flex gap-3 mt-2 text-xs text-[var(--text-muted)]">
                      <span className="flex items-center gap-1">
                        <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <path d="M19 12H5M12 5l-7 7 7 7" />
                        </svg>
                        {s.upstreamCount} upstream
                      </span>
                      <span className="flex items-center gap-1">
                        <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                          <path d="M5 12h14M12 5l7 7-7 7" />
                        </svg>
                        {s.downstreamCount} downstream
                      </span>
                    </div>
                  </button>
                ))}
              </div>

              <div className="mt-6 text-xs text-[var(--text-muted)]">
                {data.lineage.nodes.length} total nodes · {data.lineage.edges.length} edges
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
