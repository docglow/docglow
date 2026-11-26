import type { ProjectTestStatus, TestSummary } from '../../types'
import { statusColor } from '../../utils/colors'

interface Tile {
  key: ProjectTestStatus | 'total'
  label: string
  value: number
}

/**
 * Top-of-page rollup for the Tests dashboard. Failing/erroring counts lead so a
 * problem is the first thing the eye lands on; `not_run` is only shown when it
 * is non-zero (i.e. the project has never been tested, or partially).
 */
export function TestSummaryTiles({
  summary,
  activeStatus,
  onSelectStatus,
}: {
  summary: TestSummary
  activeStatus: ProjectTestStatus | 'all'
  onSelectStatus: (status: ProjectTestStatus | 'all') => void
}) {
  const s = summary.by_status
  const tiles: Tile[] = [
    { key: 'total', label: 'Total', value: summary.total },
    { key: 'fail', label: 'Failed', value: s.fail },
    { key: 'error', label: 'Errored', value: s.error },
    { key: 'warn', label: 'Warned', value: s.warn },
    { key: 'pass', label: 'Passed', value: s.pass },
  ]
  if (s.not_run > 0) tiles.push({ key: 'not_run', label: 'Not run', value: s.not_run })

  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-6">
      {tiles.map(tile => {
        const isActive =
          tile.key === 'total' ? activeStatus === 'all' : activeStatus === tile.key
        const color = tile.key === 'total' ? 'text-[var(--text)]' : statusColor(tile.key)
        return (
          <button
            key={tile.key}
            onClick={() =>
              onSelectStatus(tile.key === 'total' ? 'all' : (tile.key as ProjectTestStatus))
            }
            className={`text-left border rounded-lg p-3 transition-colors cursor-pointer
              ${isActive
                ? 'border-primary bg-primary/5'
                : 'border-[var(--border)] hover:bg-[var(--bg-surface)]'}`}
          >
            <div className={`text-2xl font-bold ${tile.value > 0 || tile.key === 'total' ? color : 'text-[var(--text-muted)]'}`}>
              {tile.value}
            </div>
            <div className="text-xs text-[var(--text-muted)] mt-0.5">{tile.label}</div>
          </button>
        )
      })}
    </div>
  )
}
