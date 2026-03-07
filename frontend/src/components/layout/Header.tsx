import { useProjectStore } from '../../stores/projectStore'
import { useSearchStore } from '../../stores/searchStore'
import { useChatStore } from '../../stores/chatStore'

export function Header() {
  const { data, theme, toggleTheme } = useProjectStore()
  const { setOpen } = useSearchStore()

  const projectName = data?.metadata.project_name ?? 'docs-plus-plus'

  return (
    <header className="h-14 border-b border-[var(--border)] bg-[var(--bg)] flex items-center px-4 gap-4 shrink-0">
      <div className="flex items-center gap-2 font-semibold text-primary">
        <span className="text-lg">d++</span>
        <span className="text-[var(--text)] font-medium">{projectName}</span>
      </div>

      <button
        onClick={() => setOpen(true)}
        className="flex-1 max-w-md mx-auto flex items-center gap-2 px-3 py-1.5 rounded-lg
                   border border-[var(--border)] text-[var(--text-muted)] text-sm
                   hover:border-primary/50 transition-colors cursor-pointer"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <span>Search...</span>
        <kbd className="ml-auto text-xs bg-[var(--bg-surface)] px-1.5 py-0.5 rounded border border-[var(--border)]">
          {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+K
        </kbd>
      </button>

      <button
        onClick={() => useChatStore.getState().toggleOpen()}
        className="p-2 rounded-lg hover:bg-[var(--bg-surface)] transition-colors cursor-pointer"
        title="AI Chat (Ctrl+J)"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      </button>

      <button
        onClick={toggleTheme}
        className="p-2 rounded-lg hover:bg-[var(--bg-surface)] transition-colors cursor-pointer"
        title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      >
        {theme === 'light' ? (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        )}
      </button>
    </header>
  )
}
