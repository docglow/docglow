import { useParams } from 'react-router-dom'
import { useProjectStore } from '../stores/projectStore'
import { ColumnTable } from '../components/models/ColumnTable'

export function SourcePage() {
  const { id } = useParams<{ id: string }>()
  const { getSource } = useProjectStore()

  const source = id ? getSource(decodeURIComponent(id)) : undefined

  if (!source) {
    return (
      <div className="text-[var(--text-muted)]">
        Source not found: {id ? decodeURIComponent(id) : 'unknown'}
      </div>
    )
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold">{source.source_name}.{source.name}</h1>
          <span className="px-2 py-0.5 text-xs font-medium rounded bg-success/10 text-success">
            Source
          </span>
        </div>
        <div className="text-sm text-[var(--text-muted)] flex gap-4">
          <span>{source.database}.{source.schema}</span>
          {source.loader && <span>Loader: {source.loader}</span>}
        </div>
        {source.description && (
          <p className="mt-3 text-sm leading-relaxed">{source.description}</p>
        )}
      </div>

      {source.freshness_status && (
        <div className="mb-6 p-4 border border-[var(--border)] rounded-lg bg-[var(--bg-surface)]">
          <h3 className="font-medium mb-2">Source Freshness</h3>
          <div className="text-sm flex gap-6">
            <div>
              <span className="text-[var(--text-muted)]">Status: </span>
              <span className={
                source.freshness_status === 'pass' ? 'text-success' :
                source.freshness_status === 'warn' ? 'text-warning' : 'text-danger'
              }>
                {source.freshness_status}
              </span>
            </div>
            {source.freshness_max_loaded_at && (
              <div>
                <span className="text-[var(--text-muted)]">Last loaded: </span>
                {source.freshness_max_loaded_at}
              </div>
            )}
          </div>
        </div>
      )}

      <h2 className="text-lg font-semibold mb-3">Columns ({source.columns.length})</h2>
      <ColumnTable columns={source.columns} />
    </div>
  )
}
