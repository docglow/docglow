import { useEffect, useRef, useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchStore } from '../../stores/searchStore'

export function SearchModal() {
  const { results, isOpen, selectedIndex, search, setOpen, setSelectedIndex, reset } = useSearchStore()
  const [localQuery, setLocalQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
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

  // Focus input when opening; reset local query when closing
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50)
    } else {
      setLocalQuery('')
    }
  }, [isOpen])

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  const handleInputChange = useCallback((value: string) => {
    setLocalQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!value.trim()) {
      search('')
      return
    }
    debounceRef.current = setTimeout(() => search(value), 200)
  }, [search])

  const handleSelect = useCallback((entry: { unique_id: string; resource_type: string; column_name?: string }) => {
    const isSource = entry.unique_id.startsWith('source.')
    const type = isSource ? 'source' : 'model'
    const hash = entry.resource_type === 'column' && entry.column_name
      ? `#col-${entry.column_name}`
      : ''
    navigate(`/${type}/${encodeURIComponent(entry.unique_id)}${hash}`)
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
      handleSelect(results[selectedIndex])
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
            value={localQuery}
            onChange={e => handleInputChange(e.target.value)}
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
            {results.map((result, i) => {
              const isColumn = result.resource_type === 'column'
              return (
                <li key={isColumn ? `${result.unique_id}::${result.column_name}` : result.unique_id}>
                  <button
                    onClick={() => handleSelect(result)}
                    className={`w-full text-left px-4 py-2 flex items-center gap-3 cursor-pointer
                      ${i === selectedIndex ? 'bg-primary/10' : 'hover:bg-[var(--bg-surface)]'}`}
                  >
                    <span className="text-xs font-medium uppercase text-[var(--text-muted)] w-14 shrink-0">
                      {isColumn ? 'col' : result.resource_type}
                    </span>
                    <div className="min-w-0">
                      {isColumn ? (
                        <>
                          <div className="text-sm font-medium truncate font-mono">{result.column_name}</div>
                          <div className="text-xs text-[var(--text-muted)] truncate">
                            in {result.model_name}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="text-sm font-medium truncate">{result.name}</div>
                          {result.description && (
                            <div className="text-xs text-[var(--text-muted)] truncate">
                              {result.description}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </button>
                </li>
              )
            })}
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
