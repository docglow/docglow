import type { CSSProperties, ReactNode } from 'react'
import { useProjectStore } from '../../stores/projectStore'
import { normalizeTableLayoutConfig } from '../../utils/uiConfig'

interface ResponsiveTableProps {
  children: ReactNode
  defaultMinWidth: number
  className?: string
  tableClassName?: string
}
export function ResponsiveTable({
  children,
  defaultMinWidth,
  className = '',
  tableClassName = '',
}: ResponsiveTableProps) {
  const config = useProjectStore(s => s.data?.ui?.table_layout)
  const layout = normalizeTableLayoutConfig(config)
  const minWidth = layout.mode === 'fit' ? null : layout.min_width ?? defaultMinWidth
  const frameOverflow = layout.mode === 'fit'
    ? 'overflow-hidden'
    : layout.mode === 'scroll'
      ? 'overflow-x-scroll'
      : 'overflow-x-auto'
  const tableStyle: CSSProperties | undefined = minWidth ? { minWidth } : undefined

  return (
    <div className={`border border-[var(--border)] rounded-lg ${frameOverflow} ${className}`}>
      <table
        className={`w-full text-sm ${layout.mode === 'fit' ? 'table-fixed' : ''} ${tableClassName}`}
        style={tableStyle}
      >
        {children}
      </table>
    </div>
  )
}
