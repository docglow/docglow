import { statusBgColor, type TestStatus } from '../../utils/colors'

interface TestBadgeProps {
  status: TestStatus
  label?: string
}

export function TestBadge({ status, label }: TestBadgeProps) {
  const displayLabel = label ?? status

  return (
    <span
      className={`inline-flex max-w-full items-center px-1.5 py-0.5 text-xs font-medium leading-tight rounded ${statusBgColor(status)}`}
      title={displayLabel}
    >
      <span className="min-w-0 max-w-full [overflow-wrap:anywhere]">
        {displayLabel}
      </span>
    </span>
  )
}
