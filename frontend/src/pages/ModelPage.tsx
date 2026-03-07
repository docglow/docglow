import { useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useProjectStore } from '../stores/projectStore'
import { ColumnTable } from '../components/models/ColumnTable'
import { SqlViewer } from '../components/models/SqlViewer'
import { TestBadge } from '../components/tests/TestBadge'
import { LineageGraph } from '../components/lineage/LineageGraph'
import { materializationLabel } from '../utils/colors'
import { getSubgraph } from '../utils/graph'

type Tab = 'columns' | 'sql' | 'lineage' | 'tests'

export function ModelPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data, getModel } = useProjectStore()
  const [activeTab, setActiveTab] = useState<Tab>('columns')
  const [sqlMode, setSqlMode] = useState<'compiled' | 'raw'>('compiled')

  const decodedId = id ? decodeURIComponent(id) : ''
  const model = decodedId ? getModel(decodedId) : undefined

  const miniLineage = useMemo(() => {
    if (!data || !decodedId) return { nodes: [], edges: [] }
    return getSubgraph(decodedId, data.lineage.nodes, data.lineage.edges, 2)
  }, [data, decodedId])

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
    <div className="max-w-5xl">
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
          <span>{model.database}.{model.schema}</span>
          <span>{model.path}</span>
        </div>
        {model.description && (
          <p className="mt-3 text-sm leading-relaxed">{model.description}</p>
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
            <div>
              <h3 className="font-medium text-[var(--text-muted)] mb-1">Depends on</h3>
              <div className="flex flex-wrap gap-1">
                {model.depends_on.map(dep => {
                  const name = dep.split('.').pop()!
                  const type = dep.startsWith('source.') ? 'source' : 'model'
                  return (
                    <button key={dep}
                            onClick={() => navigate(`/${type}/${encodeURIComponent(dep)}`)}
                            className="px-2 py-0.5 rounded bg-primary/5 text-primary text-xs
                                       hover:bg-primary/10 transition-colors cursor-pointer">
                      {name}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
          {model.referenced_by.length > 0 && (
            <div>
              <h3 className="font-medium text-[var(--text-muted)] mb-1">Referenced by</h3>
              <div className="flex flex-wrap gap-1">
                {model.referenced_by.map(ref => {
                  const name = ref.split('.').pop()!
                  const type = ref.startsWith('source.') ? 'source' : 'model'
                  return (
                    <button key={ref}
                            onClick={() => navigate(`/${type}/${encodeURIComponent(ref)}`)}
                            className="px-2 py-0.5 rounded bg-primary/5 text-primary text-xs
                                       hover:bg-primary/10 transition-colors cursor-pointer">
                      {name}
                    </button>
                  )
                })}
              </div>
            </div>
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
      {activeTab === 'columns' && <ColumnTable columns={model.columns} />}

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
        <div className="h-96">
          <LineageGraph
            nodes={miniLineage.nodes}
            edges={miniLineage.edges}
            highlightId={decodedId}
          />
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
