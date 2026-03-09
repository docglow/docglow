import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../stores/projectStore'
import type { LineageNode, LayerDefinition } from '../types'

export function LayersPage() {
  const { data } = useProjectStore()
  const navigate = useNavigate()
  const [showOnlyAuto, setShowOnlyAuto] = useState(true)
  const [selectedLayer, setSelectedLayer] = useState<number | null>(null)

  const layerConfig = data?.lineage.layer_config ?? []
  const layerMap = useMemo(() => {
    const m = new Map<number, LayerDefinition>()
    for (const l of layerConfig) m.set(l.rank, l)
    return m
  }, [layerConfig])

  const { autoNodes, ruleNodes, statsByLayer } = useMemo(() => {
    if (!data) return { autoNodes: [], ruleNodes: [], statsByLayer: new Map() }

    const auto: LineageNode[] = []
    const rule: LineageNode[] = []
    const stats = new Map<number, { total: number; auto: number; rule: number }>()

    for (const n of data.lineage.nodes) {
      if (n.layer == null) continue
      const entry = stats.get(n.layer) ?? { total: 0, auto: 0, rule: 0 }
      entry.total += 1

      if (n.layer_auto) {
        auto.push(n)
        entry.auto += 1
      } else {
        rule.push(n)
        entry.rule += 1
      }
      stats.set(n.layer, entry)
    }

    auto.sort((a, b) => a.name.localeCompare(b.name))
    return { autoNodes: auto, ruleNodes: rule, statsByLayer: stats }
  }, [data])

  const displayedNodes = useMemo(() => {
    const base = showOnlyAuto ? autoNodes : [...autoNodes, ...ruleNodes]
    if (selectedLayer == null) return base
    return base.filter(n => n.layer === selectedLayer)
  }, [autoNodes, ruleNodes, showOnlyAuto, selectedLayer])

  if (!data) return null

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto py-8 px-4">
        <h1 className="text-2xl font-bold mb-1">Lineage Layers</h1>
        <p className="text-sm text-[var(--text-muted)] mb-6">
          View how models are assigned to layers. Auto-assigned models were placed by neighbor inference rather than matching a naming or folder convention.
        </p>

        {/* Layer summary cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-8">
          {layerConfig.map(l => {
            const stats = statsByLayer.get(l.rank)
            const isSelected = selectedLayer === l.rank
            return (
              <button
                key={l.rank}
                onClick={() => setSelectedLayer(isSelected ? null : l.rank)}
                className={`text-left p-3 rounded-lg border transition-colors cursor-pointer
                  ${isSelected
                    ? 'border-primary bg-primary/5'
                    : 'border-[var(--border)] bg-[var(--bg-surface)] hover:border-primary/50'
                  }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className="w-3 h-3 rounded-sm"
                    style={{ background: l.color, opacity: 0.7 }}
                  />
                  <span className="text-sm font-semibold capitalize">{l.name}</span>
                </div>
                <div className="text-xs text-[var(--text-muted)]">
                  {stats?.total ?? 0} total
                  {stats?.auto ? ` · ${stats.auto} auto` : ''}
                </div>
              </button>
            )
          })}
        </div>

        {/* Filter toggle */}
        <div className="flex items-center gap-3 mb-4">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={showOnlyAuto}
              onChange={() => setShowOnlyAuto(v => !v)}
              className="accent-[var(--primary)]"
            />
            Show only auto-assigned models
          </label>
          <span className="text-xs text-[var(--text-muted)]">
            {displayedNodes.length} models
          </span>
        </div>

        {/* Models table */}
        {displayedNodes.length === 0 ? (
          <div className="text-sm text-[var(--text-muted)] py-8 text-center">
            {showOnlyAuto
              ? 'All models matched a layer convention — none were auto-assigned.'
              : 'No models to display.'}
          </div>
        ) : (
          <div className="border border-[var(--border)] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--bg-surface)] border-b border-[var(--border)]">
                  <th className="text-left px-3 py-2 font-medium">Model</th>
                  <th className="text-left px-3 py-2 font-medium">Folder</th>
                  <th className="text-left px-3 py-2 font-medium">Type</th>
                  <th className="text-left px-3 py-2 font-medium">Assigned Layer</th>
                  <th className="text-left px-3 py-2 font-medium">Method</th>
                </tr>
              </thead>
              <tbody>
                {displayedNodes.map(n => {
                  const layerDef = n.layer != null ? layerMap.get(n.layer) : null
                  return (
                    <tr
                      key={n.id}
                      onClick={() => {
                        const type = n.resource_type === 'source' ? 'source' : 'model'
                        navigate(`/${type}/${encodeURIComponent(n.id)}`)
                      }}
                      className="border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--bg-surface)] cursor-pointer transition-colors"
                    >
                      <td className="px-3 py-2 font-medium">{n.name}</td>
                      <td className="px-3 py-2 text-[var(--text-muted)]">{n.folder || '—'}</td>
                      <td className="px-3 py-2">
                        <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--bg-surface)] text-[var(--text-muted)]">
                          {n.resource_type}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        {layerDef ? (
                          <span className="flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-sm inline-block"
                              style={{ background: layerDef.color, opacity: 0.7 }}
                            />
                            <span className="capitalize">{layerDef.name}</span>
                          </span>
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          n.layer_auto
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        }`}>
                          {n.layer_auto ? 'auto' : 'rule'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
