import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { healthActions } from '../../utils/healthActions'
import type { HealthData } from '../../types'

/**
 * Health as outstanding work, not as a verdict.
 *
 * The letter grade lives on the Health page. Leading with it here means a
 * reader's first interaction with their own docs is being marked out of 100,
 * before the tool has shown them anything worth having.
 */
export function HealthStrip({ health }: { health: HealthData }) {
  const navigate = useNavigate()
  const actions = useMemo(() => healthActions(health), [health])

  return (
    <button
      onClick={() => navigate('/health')}
      className="w-full mb-8 px-4 py-3 flex items-center justify-between gap-4 text-left
                 border border-[var(--border)] rounded-lg bg-[var(--bg-surface)]
                 hover:border-primary/30 cursor-pointer transition-colors"
    >
      <span className="text-sm text-[var(--text-muted)] truncate">
        {actions.length > 0 ? (
          actions.map((action, i) => (
            <span key={action.key}>
              {i > 0 && <span className="mx-2" aria-hidden="true">·</span>}
              <span className="text-[var(--text)] font-medium">{action.text}</span>
            </span>
          ))
        ) : (
          <span>Nothing outstanding — documentation, tests and lineage all check out.</span>
        )}
      </span>
      <span className="text-sm text-primary shrink-0">Project health →</span>
    </button>
  )
}
