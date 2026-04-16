import { useState, useRef, useEffect, useCallback } from 'react'
import type { LineageNode } from '../../types'
import { resolveDbtSelection } from '../../utils/dbtSelect'

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
  onPinMany?: (ids: string[]) => void
  onUnpin: (id: string) => void
  onClearAll: () => void
  nodes: LineageNode[]
}

export function PinBar({ pinnedIds, onPin, onPinMany, onUnpin, onClearAll, nodes }: PinBarProps) {
  const [search, setSearch] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [dbtMode, setDbtMode] = useState(false)
  const [dbtError, setDbtError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const results = !dbtMode && search.length >= 1
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

  const handleDbtSubmit = useCallback(() => {
    if (!search.trim()) return
    const { matched, errors } = resolveDbtSelection(search, nodes)
    if (matched.size === 0) {
      setDbtError(errors[0] ?? 'No models matched')
      return
    }
    const ids = Array.from(matched)
    if (onPinMany) {
      onPinMany(ids)
    } else {
      ids.forEach(id => onPin(id))
    }
    setSearch('')
    setDbtError(null)
    inputRef.current?.focus()
  }, [search, nodes, onPin, onPinMany])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && dbtMode) {
      e.preventDefault()
      handleDbtSubmit()
      return
    }
    if (e.key === 'Backspace' && search === '' && pinnedNodes.length > 0) {
      onUnpin(pinnedNodes[pinnedNodes.length - 1].id)
    }
    if (e.key === 'Escape') {
      setSearch('')
      setIsOpen(false)
      setDbtError(null)
    }
  }, [dbtMode, search, pinnedNodes, onUnpin, handleDbtSubmit])

  const toggleDbtMode = useCallback(() => {
    setDbtMode(m => !m)
    setSearch('')
    setDbtError(null)
    setIsOpen(false)
    setTimeout(() => inputRef.current?.focus(), 0)
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Clear dbt error when user edits input
  useEffect(() => {
    if (dbtError) setDbtError(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const placeholder = dbtMode
    ? '+fct_orders tag:finance  (dbt selection syntax, press Enter)'
    : pinnedIds.size === 0
      ? 'Search models to pin...'
      : 'Add another model...'

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Input area with chips */}
      <div
        className={`flex flex-wrap items-center gap-1.5 px-3 py-2 border rounded-lg bg-[var(--bg)] cursor-text min-h-[40px]
          ${dbtMode ? 'border-amber-500/60' : 'border-[var(--border)]'}
          ${dbtError ? 'border-red-500/60' : ''}`}
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
          onChange={e => { setSearch(e.target.value); if (!dbtMode) setIsOpen(true) }}
          onFocus={() => { if (!dbtMode) setIsOpen(true) }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`flex-1 min-w-[160px] text-sm bg-transparent outline-none
            ${dbtMode ? 'font-mono' : ''}`}
        />
        {pinnedIds.size >= 2 && (
          <button
            onClick={(e) => { e.stopPropagation(); onClearAll() }}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] shrink-0 cursor-pointer"
          >
            Clear all
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); toggleDbtMode() }}
          title={dbtMode ? 'Switch to search mode' : 'Switch to dbt selection syntax'}
          className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-medium transition-colors cursor-pointer
            ${dbtMode
              ? 'bg-amber-500 text-white'
              : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)]'}`}
        >
          ⚡ dbt
        </button>
      </div>

      {/* dbt error */}
      {dbtError && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 px-3 py-2 text-xs text-red-500 bg-red-500/10 border border-red-500/30 rounded-lg">
          {dbtError}
        </div>
      )}

      {/* Autocomplete dropdown */}
      {isOpen && !dbtMode && results.length > 0 && (
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
