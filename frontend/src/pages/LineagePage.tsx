import { useState, useMemo } from 'react'
import { useProjectStore } from '../stores/projectStore'
import { LineageGraph } from '../components/lineage/LineageGraph'

export function LineagePage() {
  const { data } = useProjectStore()
  const [filter, setFilter] = useState('')
  const [filterType, setFilterType] = useState<string>('all')

  const filtered = useMemo(() => {
    if (!data) return { nodes: [], edges: [] }

    let nodes = data.lineage.nodes
    let edges = data.lineage.edges

    if (filterType !== 'all') {
      const typeNodes = new Set(
        nodes.filter(n => n.resource_type === filterType).map(n => n.id)
      )
      // Include nodes that connect to filtered type
      const connected = new Set(typeNodes)
      for (const e of edges) {
        if (typeNodes.has(e.source)) connected.add(e.target)
        if (typeNodes.has(e.target)) connected.add(e.source)
      }
      nodes = nodes.filter(n => connected.has(n.id))
      edges = edges.filter(e => connected.has(e.source) && connected.has(e.target))
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
      // Include neighbors
      const expanded = new Set(matchIds)
      for (const e of edges) {
        if (matchIds.has(e.source)) expanded.add(e.target)
        if (matchIds.has(e.target)) expanded.add(e.source)
      }
      nodes = nodes.filter(n => expanded.has(n.id))
      edges = edges.filter(e => expanded.has(e.source) && expanded.has(e.target))
    }

    return { nodes, edges }
  }, [data, filter, filterType])

  if (!data) return null

  const resourceTypes: { key: string; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'model', label: 'Models' },
    { key: 'source', label: 'Sources' },
    { key: 'seed', label: 'Seeds' },
    { key: 'exposure', label: 'Exposures' },
  ]

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-4 mb-4 shrink-0">
        <h1 className="text-xl font-bold">Lineage</h1>
        <input
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter by name, tag, or folder..."
          className="px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg
                     bg-[var(--bg)] outline-none focus:border-primary w-64"
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
        <span className="text-xs text-[var(--text-muted)] ml-auto">
          {filtered.nodes.length} nodes · {filtered.edges.length} edges
        </span>
      </div>
      <div className="flex-1 relative min-h-0">
        <LineageGraph nodes={filtered.nodes} edges={filtered.edges} />
      </div>
    </div>
  )
}
