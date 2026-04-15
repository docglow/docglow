import { useState, useRef, useEffect, useCallback } from 'react'
import type { LineageNode } from '../../types'

const RESOURCE_COLORS: Record<string, string> = {
  model: '#2563eb',
  source: '#16a34a',
  seed: '#6b7280',
  snapshot: '#7c3aed',
  exposure: '#d97706',
  metric: '#7c3aed',
}

interface PinBarProps {
  pinnedIds: Set<string>
  onPin: (id: string) => void
  onUnpin: (id: string) => void
  onClearAll: () => void
  nodes: LineageNode[]
}

export function PinBar({ pinnedIds, onPin, onUnpin, onClearAll, nodes }: PinBarProps) {
  const [search, setSearch] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const results = search.length >= 1
    ? nodes
        .filter(n =>
          !pinnedIds.has(n.id) &&
          (n.name.toLowerCase().includes(search.toLowerCase()) ||
           n.id.toLowerCase().includes(search.toLowerCase()))
        )
        .slice(0, 12)
    : []

  const pinnedNodes = nodes.filter(n => pinnedIds.has(n.id))

  const handleSelect = useCallback((id: string) => {
    onPin(id)
    setSearch('')
    setIsOpen(false)
    inputRef.current?.focus()
  }, [onPin])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && search === '' && pinnedNodes.length > 0) {
      onUnpin(pinnedNodes[pinnedNodes.length - 1].id)
    }
    if (e.key === 'Escape') {
      setSearch('')
      setIsOpen(false)
    }
  }, [search, pinnedNodes, onUnpin])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Input area with chips */}
      <div
        className="flex flex-wrap items-center gap-1.5 px-3 py-2 border border-[var(--border)]
                    rounded-lg bg-[var(--bg)] cursor-text min-h-[40px]"
        onClick={() => inputRef.current?.focus()}
      >
        {pinnedNodes.map(node => (
          <span
            key={node.id}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium
                       text-white shrink-0"
            style={{ backgroundColor: RESOURCE_COLORS[node.resource_type] ?? '#6b7280' }}
          >
            {node.name}
            <button
              onClick={(e) => { e.stopPropagation(); onUnpin(node.id) }}
              className="ml-0.5 hover:opacity-70 cursor-pointer"
            >
              ×
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={e => { setSearch(e.target.value); setIsOpen(true) }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={pinnedIds.size === 0 ? 'Search models to pin...' : 'Add another model...'}
          className="flex-1 min-w-[120px] text-sm bg-transparent outline-none"
        />
        {pinnedIds.size >= 2 && (
          <button
            onClick={onClearAll}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] shrink-0 cursor-pointer"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Autocomplete dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 border border-[var(--border)]
                        rounded-lg bg-[var(--bg)] shadow-lg overflow-hidden">
          <ul className="max-h-60 overflow-y-auto py-1">
            {results.map(node => (
              <li key={node.id}>
                <button
                  onClick={() => handleSelect(node.id)}
                  className="w-full text-left px-3 py-1.5 flex items-center gap-2
                             hover:bg-[var(--bg-surface)] cursor-pointer"
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: RESOURCE_COLORS[node.resource_type] ?? '#6b7280' }}
                  />
                  <span className="text-sm truncate">{node.name}</span>
                  <span className="text-xs text-[var(--text-muted)] ml-auto shrink-0">
                    {node.resource_type}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
