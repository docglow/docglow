import { useEffect } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import { MainLayout } from './components/layout/MainLayout'
import { SearchModal } from './components/search/SearchModal'
import { Overview } from './pages/Overview'
import { ModelPage } from './pages/ModelPage'
import { SourcePage } from './pages/SourcePage'
import { LineagePage } from './pages/LineagePage'
import { HealthPage } from './pages/HealthPage'
import { SearchPage } from './pages/SearchPage'
import { useProjectStore } from './stores/projectStore'
import { useSearchStore } from './stores/searchStore'
import type { DocglowData } from './types'

declare global {
  interface Window {
    __DOCGLOW_DATA__?: DocglowData
  }
}

function App() {
  const { data, loading, error, loadData, fetchData } = useProjectStore()
  const { initIndex } = useSearchStore()

  useEffect(() => {
    if (window.__DOCGLOW_DATA__) {
      loadData(window.__DOCGLOW_DATA__)
    } else {
      fetchData()
    }
  }, [loadData, fetchData])

  useEffect(() => {
    if (data) {
      initIndex(data.search_index)
    }
  }, [data, initIndex])

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-[var(--text-muted)]">Loading project data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-danger text-lg font-medium mb-2">Failed to load data</div>
          <div className="text-[var(--text-muted)] text-sm">{error}</div>
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <HashRouter>
      <SearchModal />
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<Overview />} />
          <Route path="/model/:id" element={<ModelPage />} />
          <Route path="/source/:id" element={<SourcePage />} />
          <Route path="/lineage" element={<LineagePage />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="/search" element={<SearchPage />} />
        </Route>
      </Routes>
    </HashRouter>
  )
}

export default App
