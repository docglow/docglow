import { describe, it, expect } from 'vitest'
import { healthActions } from '../utils/healthActions'
import type { HealthData } from '../types'

function metric(covered: number, total: number) {
  return { covered, total, rate: total === 0 ? 1 : covered / total }
}

function coverage(
  modelsDoc: [number, number],
  colsDoc: [number, number],
  modelsTest: [number, number],
  colsTest: [number, number],
) {
  return {
    models_documented: metric(...modelsDoc),
    columns_documented: metric(...colsDoc),
    models_tested: metric(...modelsTest),
    columns_tested: metric(...colsTest),
    by_folder: {},
    undocumented_models: [],
    untested_models: [],
  }
}

function makeHealth(overrides: Partial<HealthData> = {}): HealthData {
  return {
    score: {
      overall: 82,
      documentation: 90,
      testing: 59,
      freshness: 0,
      complexity: 100,
      naming: 86,
      orphans: 87,
      grade: 'B',
      freshness_included: false,
    },
    coverage: coverage([83, 83], [1024, 1292], [80, 83], [277, 1292]),
    complexity: { high_count: 0, total: 83, compliance_rate: 1, models: [] },
    naming: {
      total_checked: 73,
      total_models: 83,
      compliant_count: 63,
      compliance_rate: 63 / 73,
      violations: [],
    },
    orphans: Array.from({ length: 11 }, (_, i) => ({ unique_id: `m${i}`, name: `m${i}`, folder: 'models' })),
    ...overrides,
  } as HealthData
}

describe('healthActions', () => {
  it('leads with the weakest dimension, phrased as work to do', () => {
    expect(healthActions(makeHealth())).toEqual([
      { key: 'testing', text: '1015 columns with no test' },
      { key: 'naming', text: '10 models break the naming convention' },
    ])
  })

  it('never mentions the grade', () => {
    const text = healthActions(makeHealth()).map(a => a.text).join(' ')
    expect(text).not.toMatch(/\b[ABCDF]\b|\/100|grade/i)
  })

  it('reports the level that is further behind', () => {
    // Models are the worse of the two here, so models — not columns — get named.
    const health = makeHealth({
      score: { ...makeHealth().score, documentation: 10, testing: 100 },
      coverage: coverage([1, 83], [1290, 1292], [83, 83], [1292, 1292]),
    })
    expect(healthActions(health, 1)).toEqual([
      { key: 'documentation', text: '82 models missing descriptions' },
    ])
  })

  it('omits dimensions with nothing outstanding', () => {
    const health = makeHealth({
      score: { ...makeHealth().score, complexity: 100, orphans: 100 },
      complexity: { high_count: 0, total: 83, compliance_rate: 1, models: [] },
      orphans: [],
    })
    const keys = healthActions(health, 10).map(a => a.key)
    expect(keys).not.toContain('complexity')
    expect(keys).not.toContain('orphans')
  })

  it('skips freshness entirely when nothing is monitored', () => {
    // freshness_included: false — a 0 here means "not applicable", not "all stale".
    expect(healthActions(makeHealth(), 10).map(a => a.key)).not.toContain('freshness')
  })

  it('reports stale sources when freshness is monitored and failing', () => {
    const base = makeHealth()
    const health = makeHealth({
      score: { ...base.score, freshness: 20, freshness_included: true },
    })
    expect(healthActions(health, 1)).toEqual([
      { key: 'freshness', text: 'monitored sources are stale' },
    ])
  })

  it('returns nothing for a project with no outstanding work', () => {
    const perfect = makeHealth({
      score: {
        overall: 100, documentation: 100, testing: 100, freshness: 100,
        complexity: 100, naming: 100, orphans: 100, grade: 'A', freshness_included: true,
      },
      coverage: coverage([83, 83], [1292, 1292], [83, 83], [1292, 1292]),
      complexity: { high_count: 0, total: 83, compliance_rate: 1, models: [] },
      naming: { total_checked: 83, total_models: 83, compliant_count: 83, compliance_rate: 1, violations: [] },
      orphans: [],
    })
    expect(healthActions(perfect)).toEqual([])
  })

  it('honours the limit', () => {
    expect(healthActions(makeHealth(), 1)).toHaveLength(1)
  })
})
