import { useState, useMemo } from 'react'
import { useProjectStore } from '../stores/projectStore'
import { LineageGraph } from '../components/lineage/LineageGraph'

export function LineagePage() {
  const { data } = useProjectStore()
  const [filter, setFilter] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set())
  const [selectedFolders, setSelectedFolders] = useState<Set<string>>(new Set())

  const allTags = useMemo(() => {
    if (!data) return []
    const tags = new Set<string>()
    for (const n of data.lineage.nodes) {
      for (const t of n.tags) tags.add(t)
    }
    return [...tags].sort()
  }, [data])

  const allFolders = useMemo(() => {
    if (!data) return []
    const folders = new Set<string>()
    for (const n of data.lineage.nodes) {
      if (n.folder) folders.add(n.folder)
    }
    return [...folders].sort()
  }, [data])

  const toggleTag = (tag: string) => {
    setSelectedTags(prev => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }

  const toggleFolder = (folder: string) => {
    setSelectedFolders(prev => {
      const next = new Set(prev)
      if (next.has(folder)) next.delete(folder)
      else next.add(folder)
      return next
    })
  }

  const filtered = useMemo(() => {
    if (!data) return { nodes: [], edges: [] }

    let nodes = data.lineage.nodes
    let edges = data.lineage.edges

    if (filterType !== 'all') {
      const typeNodes = new Set(
        nodes.filter(n => n.resource_type === filterType).map(n => n.id)
      )
      const connected = new Set(typeNodes)
      for (const e of edges) {
        if (typeNodes.has(e.source)) connected.add(e.target)
        if (typeNodes.has(e.target)) connected.add(e.source)
      }
      nodes = nodes.filter(n => connected.has(n.id))
      edges = edges.filter(e => connected.has(e.source) && connected.has(e.target))
    }

    if (selectedTags.size > 0) {
      nodes = nodes.filter(n => n.tags.some(t => selectedTags.has(t)))
      const nodeIds = new Set(nodes.map(n => n.id))
      edges = edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    }

    if (selectedFolders.size > 0) {
      nodes = nodes.filter(n => selectedFolders.has(n.folder))
      const nodeIds = new Set(nodes.map(n => n.id))
      edges = edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    }

    if (filter) {
      const q = filter.toLowerCase()
      const matchIds = new Set(
        nodes
          .filter(n =>
            n.name.toLowerCase().includes(q) ||
            n.tags.some(t => t.toLowerCase().includes(q)) ||
            n.folder.toLowerCase().includes(q)
          )
          .map(n => n.id)
      )
      const expanded = new Set(matchIds)
      for (const e of edges) {
        if (matchIds.has(e.source)) expanded.add(e.target)
        if (matchIds.has(e.target)) expanded.add(e.source)
      }
      nodes = nodes.filter(n => expanded.has(n.id))
      edges = edges.filter(e => expanded.has(e.source) && expanded.has(e.target))
    }

    return { nodes, edges }
  }, [data, filter, filterType, selectedTags, selectedFolders])

  if (!data) return null

  const resourceTypes: { key: string; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'model', label: 'Models' },
    { key: 'source', label: 'Sources' },
    { key: 'seed', label: 'Seeds' },
    { key: 'exposure', label: 'Exposures' },
  ]

  const hasActiveFilters = selectedTags.size > 0 || selectedFolders.size > 0 || filterType !== 'all' || filter !== ''

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-4 mb-2 shrink-0 flex-wrap">
        <h1 className="text-xl font-bold">Lineage</h1>
        <input
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter by name..."
          className="px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg
                     bg-[var(--bg)] outline-none focus:border-primary w-48"
        />
        <div className="flex gap-1">
          {resourceTypes.map(rt => (
            <button
              key={rt.key}
              onClick={() => setFilterType(rt.key)}
              className={`px-3 py-1 text-xs rounded cursor-pointer transition-colors ${
                filterType === rt.key
                  ? 'bg-primary text-white'
                  : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)]'
              }`}
            >
              {rt.label}
            </button>
          ))}
        </div>
        {hasActiveFilters && (
          <button
            onClick={() => { setFilter(''); setFilterType('all'); setSelectedTags(new Set()); setSelectedFolders(new Set()) }}
            className="px-2 py-1 text-xs rounded bg-danger/10 text-danger hover:bg-danger/20 cursor-pointer transition-colors"
          >
            Clear filters
          </button>
        )}
        <span className="text-xs text-[var(--text-muted)] ml-auto">
          {filtered.nodes.length} nodes · {filtered.edges.length} edges
        </span>
      </div>

      {/* Tag and folder filters */}
      {(allTags.length > 0 || allFolders.length > 0) && (
        <div className="flex gap-4 mb-3 shrink-0 text-xs">
          {allTags.length > 0 && (
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-[var(--text-muted)] mr-1">Tags:</span>
              {allTags.map(tag => (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={`px-2 py-0.5 rounded cursor-pointer transition-colors ${
                    selectedTags.has(tag)
                      ? 'bg-primary text-white'
                      : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)]'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          )}
          {allFolders.length > 0 && (
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-[var(--text-muted)] mr-1">Folders:</span>
              {allFolders.map(folder => (
                <button
                  key={folder}
                  onClick={() => toggleFolder(folder)}
                  className={`px-2 py-0.5 rounded cursor-pointer transition-colors ${
                    selectedFolders.has(folder)
                      ? 'bg-primary text-white'
                      : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)]'
                  }`}
                >
                  {folder.split('/').pop()}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="flex-1 relative min-h-0">
        <LineageGraph nodes={filtered.nodes} edges={filtered.edges} />
      </div>
    </div>
  )
}
