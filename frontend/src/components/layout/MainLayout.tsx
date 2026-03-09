import { useState, useCallback, useRef } from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { ChatPanel } from '../ai/ChatPanel'

const MIN_WIDTH = 180
const MAX_WIDTH = 480
const DEFAULT_WIDTH = 256

export function MainLayout() {
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WIDTH)
  const [collapsed, setCollapsed] = useState(false)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    startX.current = e.clientX
    startW.current = sidebarWidth

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const delta = ev.clientX - startX.current
      const next = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startW.current + delta))
      setSidebarWidth(next)
    }
    const onMouseUp = () => {
      dragging.current = false
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [sidebarWidth])

  const toggleCollapse = useCallback(() => {
    setCollapsed(prev => !prev)
  }, [])

  return (
    <div className="h-screen flex flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <div
          className="relative shrink-0 flex"
          style={{ width: collapsed ? 0 : sidebarWidth, transition: collapsed ? 'width 0.15s ease' : undefined }}
        >
          <div
            className="h-full overflow-hidden"
            style={{ width: collapsed ? 0 : sidebarWidth, minWidth: collapsed ? 0 : sidebarWidth }}
          >
            <Sidebar />
          </div>

          {/* Drag handle */}
          {!collapsed && (
            <div
              onMouseDown={onMouseDown}
              className="absolute top-0 right-0 w-1 h-full cursor-col-resize z-10
                         hover:bg-primary/30 active:bg-primary/50 transition-colors"
            />
          )}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={toggleCollapse}
          className="shrink-0 w-5 flex items-center justify-center
                     border-r border-[var(--border)] bg-[var(--bg)]
                     hover:bg-[var(--bg-surface)] cursor-pointer transition-colors
                     text-[var(--text-muted)] hover:text-[var(--text)]"
          title={collapsed ? 'Show sidebar' : 'Hide sidebar'}
        >
          <svg
            width={12} height={12} viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth={2}
            strokeLinecap="round" strokeLinejoin="round"
            className={`transition-transform ${collapsed ? 'rotate-180' : ''}`}
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>

        <main className="flex-1 overflow-y-auto p-6 min-w-0">
          <Outlet />
        </main>
        <ChatPanel />
      </div>
    </div>
  )
}
