import { useState, useRef, useEffect, useMemo } from 'react'

interface MultiSelectDropdownProps {
  label: string
  options: string[]
  selected: Set<string>
  onToggle: (value: string) => void
  onClear: () => void
  /** Optional function to derive display label from option value */
  displayLabel?: (value: string) => string
}

export function MultiSelectDropdown({
  label,
  options,
  selected,
  onToggle,
  onClear,
  displayLabel,
}: MultiSelectDropdownProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', handleClick, true)
    document.addEventListener('click', handleClick, true)
    return () => {
      document.removeEventListener('mousedown', handleClick, true)
      document.removeEventListener('click', handleClick, true)
    }
  }, [open])

  // Focus search when opened
  useEffect(() => {
    if (open) searchRef.current?.focus()
  }, [open])

  const filtered = useMemo(() => {
    if (!search) return options
    const q = search.toLowerCase()
    return options.filter(o => o.toLowerCase().includes(q))
  }, [options, search])

  const getLabel = displayLabel ?? ((v: string) => v.split('/').pop() ?? v)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`px-2.5 py-1 text-xs rounded cursor-pointer transition-colors flex items-center gap-1.5
          ${selected.size > 0
            ? 'bg-primary text-white'
            : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)]'
          }`}
      >
        {label}
        {selected.size > 0 && (
          <span className="bg-white/20 rounded px-1 text-[10px]">{selected.size}</span>
        )}
        <svg
          width={10} height={10} viewBox="0 0 20 20" fill="currentColor"
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 w-64 max-h-72 bg-[var(--bg)] border border-[var(--border)] rounded-lg shadow-lg flex flex-col overflow-hidden">
          {/* Search */}
          <div className="p-2 border-b border-[var(--border)]">
            <input
              ref={searchRef}
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={`Search ${label.toLowerCase()}...`}
              className="w-full px-2 py-1 text-xs border border-[var(--border)] rounded
                         bg-[var(--bg)] outline-none focus:border-primary"
            />
          </div>

          {/* Options list */}
          <div className="flex-1 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <div className="px-2 py-3 text-xs text-[var(--text-muted)] text-center">No matches</div>
            ) : (
              filtered.map(option => (
                <button
                  key={option}
                  onClick={() => onToggle(option)}
                  className="w-full text-left px-2 py-1 text-xs rounded flex items-center gap-2
                             hover:bg-[var(--bg-surface)] cursor-pointer transition-colors"
                >
                  <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0
                    ${selected.has(option)
                      ? 'bg-primary border-primary'
                      : 'border-[var(--border)]'
                    }`}
                  >
                    {selected.has(option) && (
                      <svg width={8} height={8} viewBox="0 0 20 20" fill="white">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </span>
                  <span className="truncate text-[var(--text)]">{getLabel(option)}</span>
                </button>
              ))
            )}
          </div>

          {/* Footer */}
          {selected.size > 0 && (
            <div className="p-2 border-t border-[var(--border)]">
              <button
                onClick={() => { onClear(); setOpen(false); setSearch('') }}
                className="w-full px-2 py-1 text-xs rounded bg-danger/10 text-danger
                           hover:bg-danger/20 cursor-pointer transition-colors"
              >
                Clear {selected.size} selected
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
