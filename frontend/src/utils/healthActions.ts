/**
 * The health grade restated as work to do.
 *
 * A letter grade is the first thing a reader should not see. It judges their
 * project before the tool has given them anything, and there is nothing to do
 * with it. The same numbers phrased as outstanding items — "268 columns missing
 * descriptions" — carry identical information and read as a to-do list. The
 * grade still exists, on the Health page, where the reader opted into it.
 */
import type { HealthData } from '../types'
import { scoredDimensions } from './healthBreakdown'

export interface HealthAction {
  readonly key: string
  readonly text: string
}

/** The shortfall behind one dimension, or null when it has nothing outstanding. */
function actionFor(key: string, health: HealthData): string | null {
  const cov = health.coverage

  switch (key) {
    case 'documentation': {
      const m = cov.models_documented
      const c = cov.columns_documented
      // Report whichever level is further behind — the score is driven mostly by
      // column coverage, so naming the model count alone understates the gap.
      if (c.rate <= m.rate) {
        const missing = c.total - c.covered
        return missing > 0 ? `${missing} columns missing descriptions` : null
      }
      const missing = m.total - m.covered
      return missing > 0 ? `${missing} models missing descriptions` : null
    }
    case 'testing': {
      const m = cov.models_tested
      const c = cov.columns_tested
      if (c.rate <= m.rate) {
        const missing = c.total - c.covered
        return missing > 0 ? `${missing} columns with no test` : null
      }
      const missing = m.total - m.covered
      return missing > 0 ? `${missing} models with no test` : null
    }
    case 'freshness':
      // No per-source counts are published, so this stays qualitative.
      return health.score.freshness < 100 ? 'monitored sources are stale' : null
    case 'complexity': {
      const n = health.complexity.high_count
      return n > 0 ? `${n} high-complexity models` : null
    }
    case 'naming': {
      const n = health.naming.total_checked - health.naming.compliant_count
      return n > 0 ? `${n} models break the naming convention` : null
    }
    case 'orphans': {
      const n = health.orphans.length
      return n > 0 ? `${n} models with no downstream consumers` : null
    }
    default:
      return null
  }
}

/**
 * Outstanding work, worst dimension first.
 *
 * Ordering follows the dimension scores rather than raw counts, so a dimension
 * that is nearly perfect but happens to have a large denominator doesn't crowd
 * out the one actually dragging the project down.
 */
export function healthActions(health: HealthData, limit = 2): HealthAction[] {
  return scoredDimensions(health)
    .slice()
    .sort((a, b) => a.score - b.score)
    .map(dim => ({ key: dim.key, text: actionFor(dim.key, health) }))
    .filter((item): item is HealthAction => item.text !== null)
    .slice(0, limit)
}
