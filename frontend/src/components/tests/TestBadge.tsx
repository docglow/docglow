import { statusBgColor, type TestStatus } from '../../utils/colors'

interface TestBadgeProps {
  status: TestStatus
  label?: string
}

export function TestBadge({ status, label }: TestBadgeProps) {
  const displayLabel = label ?? status

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded ${statusBgColor(status)}`}>
      {displayLabel}
    </span>
  )
}
