import { useCallback } from 'react'

interface SqlViewerProps {
  sql: string
}

export function SqlViewer({ sql }: SqlViewerProps) {
  const copyToClipboard = useCallback(() => {
    navigator.clipboard.writeText(sql)
  }, [sql])

  if (!sql) {
    return <div className="text-sm text-[var(--text-muted)]">No SQL available.</div>
  }

  return (
    <div className="relative border border-[var(--border)] rounded-lg overflow-hidden">
      <button
        onClick={copyToClipboard}
        className="absolute top-2 right-2 px-2 py-1 text-xs rounded
                   bg-[var(--bg-surface)] border border-[var(--border)]
                   hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer"
      >
        Copy
      </button>
      <pre className="p-4 overflow-x-auto text-sm font-mono leading-relaxed bg-[var(--bg-surface)]">
        <code>{sql}</code>
      </pre>
    </div>
  )
}
