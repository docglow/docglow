import { describe, expect, it } from 'vitest'
import {
  biggestGap,
  freshnessIncluded,
  scoredDimensions,
} from '../utils/healthBreakdown'
import type { HealthData } from '../types'

function metric(covered: number, total: number) {
  return { covered, total, rate: total === 0 ? 1 : covered / total }
}

function makeHealth(overrides: Partial<HealthData['score']> = {},
                    coverage: Partial<HealthData['coverage']> = {},
                    rest: Partial<HealthData> = {}): HealthData {
  return {
    score: {
      overall: 83.3,
      documentation: 89.6,
      testing: 58.9,
      freshness: 0,
      complexity: 100,
      naming: 100,
      orphans: 86.7,
      grade: 'B',
      freshness_included: false,
      ...overrides,
    },
    coverage: {
      models_documented: metric(83, 83),
      columns_documented: metric(1024, 1292),
      models_tested: metric(80, 83),
      columns_tested: metric(277, 1292),
      by_folder: {},
      undocumented_models: [],
      untested_models: [],
      ...coverage,
    },
    complexity: { high_count: 0, total: 83, compliance_rate: 1, models: [] },
    naming: { total_checked: 17, compliant_count: 17, compliance_rate: 1, violations: [] },
    orphans: Array.from({ length: 11 }, (_, i) => ({
      unique_id: `m${i}`, name: `m${i}`, folder: 'models/staging',
    })),
    ...rest,
  } as HealthData
}

describe('freshnessIncluded', () => {
  it('is false when the flag is explicitly false', () => {
    expect(freshnessIncluded(makeHealth())).toBe(false)
  })

  it('is true when the flag is set', () => {
    expect(freshnessIncluded(makeHealth({ freshness_included: true }))).toBe(true)
  })

  it('defaults to true for payloads generated before the flag existed', () => {
    const health = makeHealth()
    const legacy = { ...health, score: { ...health.score } } as {
      score: Record<string, unknown>
    }
    delete legacy.score.freshness_included
    expect(freshnessIncluded(legacy as unknown as HealthData)).toBe(true)
  })
})

describe('scoredDimensions', () => {
  it('omits freshness when it was excluded from the weighted score', () => {
    const keys = scoredDimensions(makeHealth()).map(d => d.key)
    expect(keys).toEqual(['documentation', 'testing', 'complexity', 'naming', 'orphans'])
  })

  it('includes freshness when sources are monitored', () => {
    const keys = scoredDimensions(
      makeHealth({ freshness_included: true, freshness: 92 }),
    ).map(d => d.key)
    expect(keys).toContain('freshness')
  })
})

describe('biggestGap', () => {
  it('names the weakest dimension, not the weakest raw coverage rate', () => {
    // Documentation is 89.6 and testing 58.9 — testing is the real driver even
    // though models_documented reads a reassuring 100%.
    const gap = biggestGap(makeHealth())
    expect(gap?.label).toBe('Testing')
  })

  it('reports column-level shortfall when columns lag models', () => {
    expect(biggestGap(makeHealth())?.detail).toBe('1015 of 1292 columns have no test')
  })

  it('reports model-level shortfall when models lag columns', () => {
    const gap = biggestGap(
      makeHealth({ documentation: 10, testing: 100 }, {
        models_documented: metric(2, 83),
        columns_documented: metric(1292, 1292),
      }),
    )
    expect(gap).toEqual({
      label: 'Documentation',
      detail: '81 of 83 models have no description',
    })
  })

  it('reports orphan counts when orphans are the weakest dimension', () => {
    const gap = biggestGap(makeHealth({ documentation: 100, testing: 100, orphans: 86.7 }))
    expect(gap).toEqual({
      label: 'Orphans',
      detail: '11 models have no downstream consumers',
    })
  })

  it('returns null when nothing is imperfect', () => {
    const perfect = makeHealth({
      documentation: 100, testing: 100, complexity: 100, naming: 100, orphans: 100,
    })
    expect(biggestGap(perfect)).toBeNull()
  })

  it('ignores a zeroed freshness that was excluded from the score', () => {
    // freshness is 0 here but not included — it must not be named as the gap.
    expect(biggestGap(makeHealth())?.label).not.toBe('Freshness')
  })
})
