import { useMemo, useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useProjectStore } from '../stores/projectStore'
import { useTagFilterStore } from '../stores/tagFilterStore'
import { ColumnTable } from '../components/models/ColumnTable'
import { SqlViewer } from '../components/models/SqlViewer'
import { TestBadge } from '../components/tests/TestBadge'
import { LineageFlow } from '../components/lineage/LineageFlow'
import { FilterDropdown } from '../components/ui/FilterDropdown'
import type { FilterState } from '../components/ui/FilterDropdown'
import { Markdown } from '../components/Markdown'
import { materializationLabel } from '../utils/colors'
import { formatFqn } from '../utils/formatting'
import { getSubgraph, type LineageDirection } from '../utils/graph'
import { applyFilters, useFilterState, computeSubgraphOptions } from '../utils/lineageFilters'
import { buildModelColumnsMap } from '../utils/modelColumns'
import { buildDownstreamMap } from '../utils/columnLineageGraph'

const RESOURCE_TYPE_META: Record<string, { label: string; color: string; bg: string }> = {
  model:    { label: 'M', color: '#2563eb', bg: '#2563eb18' },
  source:   { label: 'S', color: '#16a34a', bg: '#16a34a18' },
  seed:     { label: 'Se', color: '#6b7280', bg: '#6b728018' },
  snapshot: { label: 'Sn', color: '#7c3aed', bg: '#7c3aed18' },
  exposure: { label: 'E', color: '#d97706', bg: '#d9770618' },
  metric:   { label: 'Mt', color: '#7c3aed', bg: '#7c3aed18' },
}

function parseDepId(id: string): { resourceType: string; name: string; navType: string } {
  const resourceType = id.split('.')[0] ?? 'model'
  const name = id.split('.').pop()!
  const navType = resourceType === 'source' ? 'source' : 'model'
  return { resourceType, name, navType }
}

const DEPENDENCY_COLLAPSE_THRESHOLD = 20

function DependencyList({
  label,
  ids,
  onNavigate,
}: {
  label: string
  ids: string[]
  onNavigate: (type: string, id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  const sorted = useMemo(() => {
    return [...ids]
      .map(id => ({ id, ...parseDepId(id) }))
      .sort((a, b) => {
        // Sort by resource type first, then alphabetically by name
        const typeOrder = ['source', 'model', 'seed', 'snapshot', 'exposure', 'metric']
        const aIdx = typeOrder.indexOf(a.resourceType)
        const bIdx = typeOrder.indexOf(b.resourceType)
        if (aIdx !== bIdx) return aIdx - bIdx
        return a.name.localeCompare(b.name)
      })
  }, [ids])

  const isCollapsible = sorted.length > DEPENDENCY_COLLAPSE_THRESHOLD
  const visible = isCollapsible && !expanded ? sorted.slice(0, DEPENDENCY_COLLAPSE_THRESHOLD) : sorted
  const hiddenCount = sorted.length - DEPENDENCY_COLLAPSE_THRESHOLD

  return (
    <div className="flex-1 min-w-0">
      <h3 className="font-medium text-[var(--text-muted)] mb-2">{label} ({ids.length})</h3>
      <div className="flex flex-wrap gap-1">
        {visible.map(dep => {
          const meta = RESOURCE_TYPE_META[dep.resourceType] ?? RESOURCE_TYPE_META.model
          return (
            <button
              key={dep.id}
              onClick={() => onNavigate(dep.navType, dep.id)}
              title={`${dep.resourceType}: ${dep.id}`}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs
                         hover:brightness-90 transition-all cursor-pointer"
              style={{ background: meta.bg, color: meta.color }}
            >
              <span
                className="inline-flex items-center justify-center rounded text-[9px] font-bold shrink-0"
                style={{
                  width: 18,
                  height: 14,
                  background: meta.color,
                  color: '#fff',
                  lineHeight: 1,
                }}
              >
                {meta.label}
              </span>
              {dep.name}
            </button>
          )
        })}
        {isCollapsible && (
          <button
            onClick={() => setExpanded(prev => !prev)}
            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                       bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)]
                       border border-[var(--border)] cursor-pointer transition-colors"
          >
            {expanded ? 'Show less' : `+${hiddenCount} more`}
          </button>
        )}
      </div>
    </div>
  )
}

type Tab = 'columns' | 'sql' | 'lineage' | 'tests'

export function ModelPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { data, getModel, getColumnLineage } = useProjectStore()
  const [activeTab, setActiveTab] = useState<Tab>('columns')
  const [sqlMode, setSqlMode] = useState<'compiled' | 'raw'>('compiled')

  const decodedId = id ? decodeURIComponent(id) : ''
  const model = decodedId ? getModel(decodedId) : undefined

  // Scroll to column anchor when navigating with a hash (e.g. #col-closer_id)
  useEffect(() => {
    const hash = location.hash
    if (!hash || !hash.startsWith('#col-')) return

    // Ensure we're on the columns tab
    setActiveTab('columns')

    // Delay to allow the tab content to render
    const timer = setTimeout(() => {
      const el = document.getElementById(hash.slice(1))
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        // Brief highlight flash
        el.style.transition = 'background-color 0.3s'
        el.style.backgroundColor = 'var(--primary-bg, rgba(37, 99, 235, 0.12))'
        setTimeout(() => { el.style.backgroundColor = '' }, 1500)
      }
    }, 100)
    return () => clearTimeout(timer)
  }, [location.hash, decodedId])

  // Lineage state
  const [depth, setDepth] = useState(2)
  const [direction, setDirection] = useState<LineageDirection>('both')
  const [lineageFullscreen, setLineageFullscreen] = useState(false)
  const [typeFilter, toggleType, setTypeMode, clearTypes] = useFilterState()
  const { selected: globalTagSelected, mode: globalTagMode, toggle: toggleTag, setMode: setTagMode, clear: clearTags } = useTagFilterStore()
  const tagFilter: FilterState = useMemo(() => ({ mode: globalTagMode, selected: new Set(globalTagSelected) }), [globalTagSelected, globalTagMode])
  const [folderFilter, toggleFolder, setFolderMode, clearFolders] = useFilterState()

  const rawSubgraph = useMemo(() => {
    if (!data || !decodedId) return { nodes: [], edges: [] }
    return getSubgraph(decodedId, data.lineage.nodes, data.lineage.edges, depth, direction)
  }, [data, decodedId, depth, direction])

  const filteredSubgraph = useMemo(() => {
    return applyFilters(rawSubgraph.nodes, rawSubgraph.edges, typeFilter, tagFilter, folderFilter)
  }, [rawSubgraph, typeFilter, tagFilter, folderFilter])

  const subgraphOptions = useMemo(() => {
    return computeSubgraphOptions(rawSubgraph.nodes)
  }, [rawSubgraph.nodes])

  const hasActiveFilters = typeFilter.selected.size > 0 || tagFilter.selected.size > 0 || folderFilter.selected.size > 0

  const clearAllFilters = useCallback(() => {
    clearTypes()
    clearTags()
    clearFolders()
  }, [clearTypes, clearTags, clearFolders])

  const modelColumnsMap = useMemo(() => {
    if (!data) return {}
    return buildModelColumnsMap(data)
  }, [data])

  if (!model) {
    return (
      <div className="text-[var(--text-muted)]">
        Model not found: {id ? decodeURIComponent(id) : 'unknown'}
      </div>
    )
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'columns', label: `Columns (${model.columns.length})` },
    { key: 'sql', label: 'SQL' },
    { key: 'lineage', label: 'Lineage' },
    { key: 'tests', label: `Tests (${model.test_results.length})` },
  ]

  const overallTestStatus = (() => {
    if (model.test_results.length === 0) return 'none' as const
    if (model.test_results.some(t => t.status === 'fail' || t.status === 'error')) return 'fail' as const
    if (model.test_results.some(t => t.status === 'warn')) return 'warn' as const
    if (model.test_results.every(t => t.status === 'pass')) return 'pass' as const
    return 'none' as const
  })()

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold">{model.name}</h1>
          <span className="px-2 py-0.5 text-xs font-medium rounded bg-primary/10 text-primary">
            {materializationLabel(model.materialization)}
          </span>
          <TestBadge status={overallTestStatus} />
        </div>
        <div className="text-sm text-[var(--text-muted)] flex gap-4">
          <span>{formatFqn({ database: model.database, schema: model.schema })}</span>
          <span>{model.path}</span>
        </div>
        {model.description && (
          <Markdown content={model.description} className="mt-3 text-sm" />
        )}
        {model.tags.length > 0 && (
          <div className="flex gap-1 mt-2">
            {model.tags.map(tag => (
              <span key={tag} className="px-2 py-0.5 text-xs rounded bg-[var(--bg-surface)] border border-[var(--border)]">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Dependencies */}
      {(model.depends_on.length > 0 || model.referenced_by.length > 0) && (
        <div className="mb-6 flex gap-8 text-sm">
          {model.depends_on.length > 0 && (
            <DependencyList
              label="Depends on"
              ids={model.depends_on}
              onNavigate={(type, id) => navigate(`/${type}/${encodeURIComponent(id)}`)}
            />
          )}
          {model.referenced_by.length > 0 && (
            <DependencyList
              label="Referenced by"
              ids={model.referenced_by}
              onNavigate={(type, id) => navigate(`/${type}/${encodeURIComponent(id)}`)}
            />
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-[var(--border)] flex gap-0 mb-4">
        {tabs.map(tab => (
          <button key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer
                    ${activeTab === tab.key
                      ? 'border-primary text-primary'
                      : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]'
                    }`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'columns' && (
        <ColumnTable
          columns={model.columns}
          columnLineage={getColumnLineage(decodedId)}
          columnDownstream={data?.column_lineage ? buildDownstreamMap(decodedId, data.column_lineage) : undefined}
          modelId={decodedId}
          columnLineageData={data?.column_lineage}
        />
      )}

      {activeTab === 'sql' && (
        <div>
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setSqlMode('compiled')}
              className={`px-3 py-1 text-xs rounded cursor-pointer ${
                sqlMode === 'compiled'
                  ? 'bg-primary text-white'
                  : 'bg-[var(--bg-surface)] text-[var(--text-muted)]'
              }`}
            >
              Compiled
            </button>
            <button
              onClick={() => setSqlMode('raw')}
              className={`px-3 py-1 text-xs rounded cursor-pointer ${
                sqlMode === 'raw'
                  ? 'bg-primary text-white'
                  : 'bg-[var(--bg-surface)] text-[var(--text-muted)]'
              }`}
            >
              Raw
            </button>
          </div>
          <SqlViewer sql={sqlMode === 'compiled' ? model.compiled_sql : model.raw_sql} />
        </div>
      )}

      {activeTab === 'lineage' && (
        <div className={lineageFullscreen
          ? 'fixed inset-0 z-50 bg-[var(--bg)] flex flex-col'
          : 'flex flex-col'
        }>
          {/* Lineage toolbar */}
          <div className="flex items-center gap-2 mb-2 flex-wrap shrink-0 px-1">
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

            {/* Direction toggle */}
            <div className="flex items-center rounded overflow-hidden border border-[var(--border)]">
              {(['upstream', 'both', 'downstream'] as const).map(dir => (
                <button
                  key={dir}
                  onClick={() => setDirection(dir)}
                  className={`px-2 py-0.5 text-xs cursor-pointer transition-colors flex items-center gap-1
                    ${direction === dir
                      ? 'bg-primary text-white'
                      : 'bg-[var(--bg)] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg-surface)]'
                    }`}
                  title={dir === 'both' ? 'Show upstream & downstream' : `Show ${dir} only`}
                >
                  {dir === 'upstream' && (
                    <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                      <path d="M19 12H5M12 5l-7 7" />
                    </svg>
                  )}
                  {dir === 'both' && (
                    <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                      <path d="M5 12h14M8 8l-4 4 4 4M16 8l4 4-4 4" />
                    </svg>
                  )}
                  {dir === 'downstream' && (
                    <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                      <path d="M5 12h14M12 5l7 7" />
                    </svg>
                  )}
                  {dir === 'upstream' ? 'Up' : dir === 'downstream' ? 'Down' : 'Both'}
                </button>
              ))}
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
              {filteredSubgraph.nodes.length} nodes · {filteredSubgraph.edges.length} edges
            </span>

            {/* Fullscreen toggle */}
            <button
              onClick={() => setLineageFullscreen(f => !f)}
              className="p-1 rounded hover:bg-[var(--bg-surface)] cursor-pointer transition-colors text-[var(--text-muted)] hover:text-[var(--text)]"
              title={lineageFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            >
              {lineageFullscreen ? (
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 3v3a2 2 0 01-2 2H3M21 8h-3a2 2 0 01-2-2V3M3 16h3a2 2 0 012 2v3M16 21v-3a2 2 0 012-2h3" />
                </svg>
              ) : (
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                </svg>
              )}
            </button>
          </div>

          {/* Graph area */}
          <div className={lineageFullscreen ? 'flex-1 relative min-h-0' : 'relative'} style={lineageFullscreen ? undefined : { height: 'calc(100vh - 380px)', minHeight: 400 }}>
            <LineageFlow
              nodes={filteredSubgraph.nodes}
              edges={filteredSubgraph.edges}
              pinnedIds={new Set([decodedId])}
              layerConfig={data?.lineage.layer_config}
              onNavigateAway={() => setLineageFullscreen(false)}
              columnLineageData={data?.column_lineage}
              modelColumns={modelColumnsMap}
            />
          </div>
        </div>
      )}

      {activeTab === 'tests' && (
        <div className="border border-[var(--border)] rounded-lg overflow-hidden">
          {model.test_results.length === 0 ? (
            <div className="p-4 text-sm text-[var(--text-muted)]">No tests defined for this model.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-surface)]">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Test</th>
                  <th className="text-left px-4 py-2 font-medium">Type</th>
                  <th className="text-left px-4 py-2 font-medium">Column</th>
                  <th className="text-left px-4 py-2 font-medium">Status</th>
                  <th className="text-right px-4 py-2 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {model.test_results.map((test, i) => (
                  <tr key={i} className="border-t border-[var(--border)]">
                    <td className="px-4 py-2 font-mono text-xs">{test.test_name}</td>
                    <td className="px-4 py-2">{test.test_type}</td>
                    <td className="px-4 py-2">{test.column_name ?? '—'}</td>
                    <td className="px-4 py-2">
                      <TestBadge status={test.status} />
                    </td>
                    <td className="px-4 py-2 text-right text-[var(--text-muted)]">
                      {(test.execution_time * 1000).toFixed(0)}ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
