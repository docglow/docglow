import MiniSearch from 'minisearch'
import { create } from 'zustand'
import type { SearchEntry } from '../types'

const RESOURCE_RESULT_THRESHOLD = 5
const MAX_RESULTS = 20

interface SearchState {
  query: string
  results: SearchEntry[]
  isOpen: boolean
  selectedIndex: number

  initIndex: (entries: SearchEntry[]) => void
  search: (query: string) => void
  setOpen: (open: boolean) => void
  setSelectedIndex: (index: number) => void
  reset: () => void
}

let resourceIndex: MiniSearch<SearchEntry> | null = null
let columnIndex: MiniSearch<SearchEntry> | null = null

function buildIndex(
  entries: SearchEntry[],
  fields: string[],
  storeFields: string[],
  boost: Record<string, number>,
): MiniSearch<SearchEntry> {
  const index = new MiniSearch<SearchEntry>({
    fields,
    storeFields,
    idField: 'id',
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
      boost,
    },
  })
  index.addAll(entries)
  return index
}

export const useSearchStore = create<SearchState>((set, get) => ({
  query: '',
  results: [],
  isOpen: false,
  selectedIndex: 0,

  initIndex: (entries) => {
    const resources = entries.filter(e => e.resource_type !== 'column')
    const columns = entries.filter(e => e.resource_type === 'column')

    resourceIndex = buildIndex(
      resources,
      ['name', 'description', 'tags'],
      ['id', 'unique_id', 'name', 'resource_type', 'description', 'tags'],
      { name: 2 },
    )

    columnIndex = buildIndex(
      columns,
      ['name', 'description', 'model_name'],
      ['id', 'unique_id', 'name', 'resource_type', 'column_name', 'model_name', 'description'],
      { name: 2 },
    )
  },

  search: (query) => {
    if (!resourceIndex || !query.trim()) {
      set({ query, results: [], selectedIndex: 0 })
      return
    }

    // Search resources first (fast — typically ~3K entries)
    const resourceResults = resourceIndex.search(query, { limit: MAX_RESULTS }) as unknown as SearchEntry[]

    let results: SearchEntry[]

    // If few resource results, also search columns to fill the list
    if (resourceResults.length < RESOURCE_RESULT_THRESHOLD && columnIndex) {
      const remaining = MAX_RESULTS - resourceResults.length
      const columnResults = columnIndex.search(query, { limit: remaining }) as unknown as SearchEntry[]
      results = [...resourceResults, ...columnResults]
    } else {
      results = resourceResults.slice(0, MAX_RESULTS)
    }

    set({ query, results, selectedIndex: 0 })
  },

  setOpen: (open) => set({ isOpen: open }),

  setSelectedIndex: (index) => set({ selectedIndex: index }),

  reset: () => set({ query: '', results: [], isOpen: false, selectedIndex: 0 }),
}))
