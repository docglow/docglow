import { create } from 'zustand'
import type { DatumData, DatumModel, DatumSource } from '../types'

interface ProjectState {
  data: DatumData | null
  loading: boolean
  error: string | null
  theme: 'light' | 'dark'

  loadData: (data: DatumData) => void
  fetchData: (url?: string) => Promise<void>
  setTheme: (theme: 'light' | 'dark') => void
  toggleTheme: () => void

  getModel: (uniqueId: string) => DatumModel | undefined
  getSource: (uniqueId: string) => DatumSource | undefined
  getResource: (uniqueId: string) => DatumModel | DatumSource | undefined
}

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem('dpp-theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem('dpp-theme', theme)
}

export const useProjectStore = create<ProjectState>((set, get) => {
  const initialTheme = getInitialTheme()
  applyTheme(initialTheme)

  return {
    data: null,
    loading: false,
    error: null,
    theme: initialTheme,

    loadData: (data) => set({ data, loading: false, error: null }),

    fetchData: async (url = './datum-data.json') => {
      set({ loading: true, error: null })
      try {
        const response = await fetch(url)
        if (!response.ok) {
          throw new Error(`Failed to load data: ${response.status}`)
        }
        const data: DatumData = await response.json()
        set({ data, loading: false, error: null })
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load project data'
        set({ loading: false, error: message })
      }
    },

    setTheme: (theme) => {
      applyTheme(theme)
      set({ theme })
    },

    toggleTheme: () => {
      const next = get().theme === 'light' ? 'dark' : 'light'
      applyTheme(next)
      set({ theme: next })
    },

    getModel: (uniqueId) => {
      const { data } = get()
      if (!data) return undefined
      return data.models[uniqueId] ?? data.seeds[uniqueId] ?? data.snapshots[uniqueId]
    },

    getSource: (uniqueId) => {
      const { data } = get()
      if (!data) return undefined
      return data.sources[uniqueId]
    },

    getResource: (uniqueId) => {
      const { data } = get()
      if (!data) return undefined
      return (
        data.models[uniqueId] ??
        data.sources[uniqueId] ??
        data.seeds[uniqueId] ??
        data.snapshots[uniqueId]
      )
    },
  }
})
