/**
 * Decompose a health grade into the dimensions that produced it.
 *
 * The overall score is a weighted blend of per-dimension scores, and those
 * scores are driven largely by *column*-level coverage. Surfacing model-level
 * coverage rates next to the grade leaves a reader unable to explain why the
 * grade is what it is — e.g. "100% documented" sitting beside a B.
 */
import type { HealthData } from '../types'

export interface Dimension {
  readonly key: string
  readonly label: string
  readonly score: number
}

/** Freshness is excluded from the weighted score when nothing is monitored. */
export function freshnessIncluded(health: HealthData): boolean {
  return health.score.freshness_included !== false
}

/** The dimensions that actually contribute to the overall score, in report order. */
export function scoredDimensions(health: HealthData): Dimension[] {
  const s = health.score
  const dims: Dimension[] = [
    { key: 'documentation', label: 'Docs', score: s.documentation },
    { key: 'testing', label: 'Tests', score: s.testing },
  ]
  if (freshnessIncluded(health)) {
    dims.push({ key: 'freshness', label: 'Freshness', score: s.freshness })
  }
  dims.push(
    { key: 'complexity', label: 'Complexity', score: s.complexity },
    { key: 'naming', label: 'Naming', score: s.naming },
    { key: 'orphans', label: 'Orphans', score: s.orphans },
  )
  return dims
}

/**
 * The weakest contributing dimension, with the concrete shortfall behind it.
 * Returns null when every dimension is perfect — there is no gap to name.
 */
export function biggestGap(health: HealthData): { label: string; detail: string } | null {
  const dims = scoredDimensions(health)
  const weakest = dims.reduce((a, b) => (b.score < a.score ? b : a))
  if (weakest.score >= 100) return null

  const cov = health.coverage
  switch (weakest.key) {
    case 'documentation': {
      const m = cov.models_documented
      const c = cov.columns_documented
      return c.rate <= m.rate
        ? { label: 'Documentation', detail: `${c.total - c.covered} of ${c.total} columns have no description` }
        : { label: 'Documentation', detail: `${m.total - m.covered} of ${m.total} models have no description` }
    }
    case 'testing': {
      const m = cov.models_tested
      const c = cov.columns_tested
      return c.rate <= m.rate
        ? { label: 'Testing', detail: `${c.total - c.covered} of ${c.total} columns have no test` }
        : { label: 'Testing', detail: `${m.total - m.covered} of ${m.total} models have no test` }
    }
    case 'freshness':
      return { label: 'Freshness', detail: 'some monitored sources are stale' }
    case 'complexity':
      return {
        label: 'Complexity',
        detail: `${health.complexity.high_count} of ${health.complexity.total} models are high complexity`,
      }
    case 'naming': {
      const n = health.naming
      return {
        label: 'Naming',
        detail: `${n.total_checked - n.compliant_count} of ${n.total_checked} models break the naming convention`,
      }
    }
    case 'orphans':
      return {
        label: 'Orphans',
        detail: `${health.orphans.length} models have no downstream consumers`,
      }
    default:
      return null
  }
}
