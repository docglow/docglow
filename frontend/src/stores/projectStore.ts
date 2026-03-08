import { create } from 'zustand'
import type { DocglowData, DocglowModel, DocglowSource } from '../types'
import { useChatStore } from './chatStore'

interface ProjectState {
  data: DocglowData | null
  loading: boolean
  error: string | null
  theme: 'light' | 'dark'

  loadData: (data: DocglowData) => void
  fetchData: (url?: string) => Promise<void>
  setTheme: (theme: 'light' | 'dark') => void
  toggleTheme: () => void

  getModel: (uniqueId: string) => DocglowModel | undefined
  getSource: (uniqueId: string) => DocglowSource | undefined
  getResource: (uniqueId: string) => DocglowModel | DocglowSource | undefined
}

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem('dg-theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.setItem('dg-theme', theme)
}

function _applyEmbeddedAiKey(data: DocglowData) {
  if (data.ai_key && !useChatStore.getState().apiKey) {
    useChatStore.getState().setApiKey(data.ai_key)
  }
}

export const useProjectStore = create<ProjectState>((set, get) => {
  const initialTheme = getInitialTheme()
  applyTheme(initialTheme)

  return {
    data: null,
    loading: false,
    error: null,
    theme: initialTheme,

    loadData: (data) => {
      set({ data, loading: false, error: null })
      _applyEmbeddedAiKey(data)
    },

    fetchData: async (url = './docglow-data.json') => {
      set({ loading: true, error: null })
      try {
        const response = await fetch(url)
        if (!response.ok) {
          throw new Error(`Failed to load data: ${response.status}`)
        }
        const data: DocglowData = await response.json()
        set({ data, loading: false, error: null })
        _applyEmbeddedAiKey(data)
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
