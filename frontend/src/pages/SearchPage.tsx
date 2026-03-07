import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useSearchStore } from '../stores/searchStore'

export function SearchPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { results, search } = useSearchStore()
  const [localQuery, setLocalQuery] = useState(searchParams.get('q') ?? '')

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setLocalQuery(q)
      search(q)
    }
  }, [searchParams, search])

  const handleSearch = (q: string) => {
    setLocalQuery(q)
    search(q)
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-bold mb-4">Search</h1>
      <input
        type="text"
        value={localQuery}
        onChange={e => handleSearch(e.target.value)}
        placeholder="Search models, columns, sources..."
        className="w-full px-4 py-2 text-sm border border-[var(--border)] rounded-lg
                   bg-[var(--bg)] outline-none focus:border-primary mb-6"
        autoFocus
      />

      {results.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-[var(--text-muted)] mb-3">
            {results.length} result{results.length !== 1 ? 's' : ''}
          </p>
          {results.map(result => {
            const type = result.resource_type === 'source' ? 'source' : 'model'
            return (
              <button
                key={result.unique_id}
                onClick={() => navigate(`/${type}/${encodeURIComponent(result.unique_id)}`)}
                className="w-full text-left p-4 border border-[var(--border)] rounded-lg
                           hover:border-primary/50 transition-colors cursor-pointer block"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium uppercase px-1.5 py-0.5 rounded
                                   bg-[var(--bg-surface)] text-[var(--text-muted)]">
                    {result.resource_type}
                  </span>
                  <span className="font-medium text-primary">{result.name}</span>
                </div>
                {result.description && (
                  <p className="text-sm text-[var(--text-muted)] line-clamp-2">
                    {result.description}
                  </p>
                )}
                {result.columns && (
                  <p className="text-xs text-[var(--text-muted)] mt-1 truncate">
                    Columns: {result.columns}
                  </p>
                )}
              </button>
            )
          })}
        </div>
      )}

      {localQuery && results.length === 0 && (
        <p className="text-sm text-[var(--text-muted)]">
          No results for "{localQuery}"
        </p>
      )}
    </div>
  )
}
