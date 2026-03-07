import { useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchStore } from '../../stores/searchStore'

export function SearchModal() {
  const { query, results, isOpen, selectedIndex, search, setOpen, setSelectedIndex, reset } = useSearchStore()
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Cmd+K to open
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(!isOpen)
      }
      if (e.key === 'Escape' && isOpen) {
        reset()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, setOpen, reset])

  // Focus input when opening
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  const handleSelect = useCallback((uniqueId: string, resourceType: string) => {
    const type = resourceType === 'source' ? 'source' : 'model'
    navigate(`/${type}/${encodeURIComponent(uniqueId)}`)
    reset()
  }, [navigate, reset])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(Math.min(selectedIndex + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(Math.max(selectedIndex - 1, 0))
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      handleSelect(results[selectedIndex].unique_id, results[selectedIndex].resource_type)
    }
  }, [selectedIndex, results, setSelectedIndex, handleSelect])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
         onClick={() => reset()}>
      <div className="absolute inset-0 bg-black/50" />
      <div className="relative w-full max-w-lg bg-[var(--bg)] border border-[var(--border)]
                      rounded-xl shadow-2xl overflow-hidden"
           onClick={e => e.stopPropagation()}>
        <div className="flex items-center px-4 border-b border-[var(--border)]">
          <svg className="w-5 h-5 text-[var(--text-muted)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => search(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search models, columns, sources..."
            className="w-full px-3 py-3 text-sm bg-transparent outline-none"
          />
          <kbd className="text-xs text-[var(--text-muted)] bg-[var(--bg-surface)] px-1.5 py-0.5 rounded border border-[var(--border)]">
            esc
          </kbd>
        </div>

        {results.length > 0 && (
          <ul className="max-h-80 overflow-y-auto py-2">
            {results.map((result, i) => (
              <li key={result.unique_id}>
                <button
                  onClick={() => handleSelect(result.unique_id, result.resource_type)}
                  className={`w-full text-left px-4 py-2 flex items-center gap-3 cursor-pointer
                    ${i === selectedIndex ? 'bg-primary/10' : 'hover:bg-[var(--bg-surface)]'}`}
                >
                  <span className="text-xs font-medium uppercase text-[var(--text-muted)] w-14 shrink-0">
                    {result.resource_type}
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{result.name}</div>
                    {result.description && (
                      <div className="text-xs text-[var(--text-muted)] truncate">
                        {result.description}
                      </div>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}

        {query && results.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            No results for "{query}"
          </div>
        )}
      </div>
    </div>
  )
}
