import { create } from 'zustand'
import type { FilterMode } from '../components/ui/FilterDropdown'

interface TagFilterState {
  readonly mode: FilterMode
  readonly selected: ReadonlySet<string>
  readonly toggle: (tag: string) => void
  readonly setMode: (mode: FilterMode) => void
  readonly clear: () => void
  readonly setFromParams: (tags: readonly string[], mode: FilterMode) => void
}

function writeToUrl(selected: ReadonlySet<string>, mode: FilterMode) {
  if (typeof window === 'undefined') return

  const hash = window.location.hash
  const hashIndex = hash.indexOf('?')
  const basePath = hashIndex >= 0 ? hash.slice(0, hashIndex) : hash
  const params = new URLSearchParams(hashIndex >= 0 ? hash.slice(hashIndex + 1) : '')

  if (selected.size > 0) {
    params.set('tags', [...selected].sort().join(','))
    if (mode !== 'include') {
      params.set('tagMode', mode)
    } else {
      params.delete('tagMode')
    }
  } else {
    params.delete('tags')
    params.delete('tagMode')
  }

  const qs = params.toString()
  const newHash = qs ? `${basePath}?${qs}` : basePath
  window.history.replaceState(null, '', newHash || '#/')
}

/** Parse tag filter state from URL hash params. Defaults to include mode. */
export function readTagsFromUrl(): { tags: string[]; mode: FilterMode } {
  if (typeof window === 'undefined') return { tags: [], mode: 'include' }

  const hash = window.location.hash
  const qIndex = hash.indexOf('?')
  if (qIndex < 0) return { tags: [], mode: 'include' }

  const params = new URLSearchParams(hash.slice(qIndex + 1))
  const raw = params.get('tags')
  const mode = params.get('tagMode') === 'exclude' ? 'exclude' : 'include'
  const tags = raw ? raw.split(',').filter(Boolean) : []

  return { tags, mode }
}

export const useTagFilterStore = create<TagFilterState>((set, get) => {
  const initial = readTagsFromUrl()

  return {
    mode: initial.mode,
    selected: new Set(initial.tags),

    toggle: (tag) => {
      const state = get()
      const next = new Set(state.selected)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      set({ selected: next })
      writeToUrl(next, state.mode)
    },

    setMode: (mode) => {
      const { selected } = get()
      set({ mode })
      writeToUrl(selected, mode)
    },

    clear: () => {
      set({ selected: new Set<string>(), mode: 'include' })
      writeToUrl(new Set(), 'include')
    },

    setFromParams: (tags, mode) => {
      const selected = new Set(tags)
      set({ selected, mode })
      writeToUrl(selected, mode)
    },
  }
})
