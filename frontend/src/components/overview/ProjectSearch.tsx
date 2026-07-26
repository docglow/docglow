import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchStore } from '../../stores/searchStore'
import { buildResourcePath } from '../../utils/resourceRoutes'

const INLINE_RESULT_LIMIT = 6

/**
 * The landing page's primary action.
 *
 * Finding one specific model is the most common reason anyone opens dbt docs,
 * so it gets the top of the page rather than a keyboard shortcut. Results
 * appear inline; Enter with no selection falls through to the full search page.
 */
export function ProjectSearch() {
  const navigate = useNavigate()
  const { results, search, reset } = useSearchStore()
  const [query, setQuery] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // The store is shared with the ⌘K modal — leave it clean on the way out so
  // the modal doesn't open pre-filled with whatever was typed here.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      reset()
    }
  }, [reset])

  const handleChange = useCallback((value: string) => {
    setQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!value.trim()) {
      search('')
      return
    }
    debounceRef.current = setTimeout(() => search(value), 150)
  }, [search])

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}`)
  }, [navigate, query])

  const visible = query.trim() ? results.slice(0, INLINE_RESULT_LIMIT) : []

  return (
    <div className="mb-8">
      <form onSubmit={handleSubmit} role="search">
        <input
          type="search"
          value={query}
          onChange={e => handleChange(e.target.value)}
          placeholder="Search models, columns, sources…"
          aria-label="Search this project"
          className="w-full px-4 py-3 text-base border border-[var(--border)] rounded-lg
                     bg-[var(--bg-surface)] outline-none focus:border-primary
                     placeholder:text-[var(--text-muted)]"
        />
      </form>

      {visible.length > 0 && (
        <ul
          aria-label="Search results"
          className="mt-2 border border-[var(--border)] rounded-lg overflow-hidden"
        >
          {visible.map(result => (
            <li key={result.unique_id}>
              <button
                onClick={() => navigate(buildResourcePath(result.unique_id))}
                className="w-full text-left px-4 py-2 flex items-center gap-2
                           border-b border-[var(--border)] last:border-b-0
                           hover:bg-[var(--bg-surface)] cursor-pointer transition-colors"
              >
                <span className="text-xs font-medium uppercase px-1.5 py-0.5 rounded shrink-0
                                 bg-[var(--bg-surface)] text-[var(--text-muted)]">
                  {result.resource_type}
                </span>
                {/* The name is what the reader is scanning for, so it never
                    gives up width to the description beside it. */}
                <span className="font-medium text-primary shrink-0">{result.name}</span>
                {result.description && (
                  <span className="text-xs text-[var(--text-muted)] truncate min-w-0">
                    {result.description}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {query.trim() && visible.length === 0 && (
        <p className="mt-2 text-sm text-[var(--text-muted)]">No results for "{query.trim()}"</p>
      )}
    </div>
  )
}
