import Fuse, { type IFuseOptions } from 'fuse.js'
import { create } from 'zustand'
import type { SearchEntry } from '../types'

interface SearchState {
  query: string
  results: SearchEntry[]
  isOpen: boolean
  selectedIndex: number
  fuse: Fuse<SearchEntry> | null

  initIndex: (entries: SearchEntry[]) => void
  search: (query: string) => void
  setOpen: (open: boolean) => void
  setSelectedIndex: (index: number) => void
  reset: () => void
}

const FUSE_OPTIONS: IFuseOptions<SearchEntry> = {
  keys: [
    { name: 'name', weight: 0.4 },
    { name: 'description', weight: 0.25 },
    { name: 'columns', weight: 0.15 },
    { name: 'tags', weight: 0.1 },
    { name: 'sql_snippet', weight: 0.1 },
  ],
  threshold: 0.4,
  includeMatches: true,
  minMatchCharLength: 2,
}

export const useSearchStore = create<SearchState>((set, get) => ({
  query: '',
  results: [],
  isOpen: false,
  selectedIndex: 0,
  fuse: null,

  initIndex: (entries) => {
    const fuse = new Fuse(entries, FUSE_OPTIONS)
    set({ fuse })
  },

  search: (query) => {
    const { fuse } = get()
    if (!fuse || !query.trim()) {
      set({ query, results: [], selectedIndex: 0 })
      return
    }
    const fuseResults = fuse.search(query, { limit: 20 })
    const results = fuseResults.map((r) => r.item)
    set({ query, results, selectedIndex: 0 })
  },

  setOpen: (open) => set({ isOpen: open }),

  setSelectedIndex: (index) => set({ selectedIndex: index }),

  reset: () => set({ query: '', results: [], isOpen: false, selectedIndex: 0 }),
}))
