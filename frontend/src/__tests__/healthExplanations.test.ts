import { describe, expect, it } from 'vitest'
import {
  complexityExplanation,
  explanationFor,
  namingExplanation,
  orphansExplanation,
  overallExplanation,
} from '../utils/healthExplanations'
import type { HealthData } from '../types'

function metric(covered: number, total: number) {
  return { covered, total, rate: total === 0 ? 1 : covered / total }
}

function makeHealth(overrides: Partial<HealthData> = {}): HealthData {
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
    },
    coverage: {
      models_documented: metric(83, 83),
      columns_documented: metric(1024, 1292),
      models_tested: metric(80, 83),
      columns_tested: metric(277, 1292),
      by_folder: {},
      undocumented_models: [],
      untested_models: [],
    },
    complexity: { high_count: 0, total: 83, compliance_rate: 1, models: [] },
    naming: {
      total_checked: 17,
      total_models: 83,
      compliant_count: 17,
      compliance_rate: 1,
      violations: [],
    },
    orphans: [],
    config: {
      weights: {
        documentation: 0.25, testing: 0.25, freshness: 0.15,
        complexity: 0.15, naming: 0.1, orphans: 0.1,
      },
      complexity_thresholds: {
        high_sql_lines: 200, high_join_count: 8,
        high_cte_count: 10, high_subquery_count: 5,
      },
      naming_rules: [
        { layer: 'staging', patterns: ['^stg_'] },
        { layer: 'intermediate', patterns: ['^int_'] },
        { layer: 'marts', patterns: ['^fct_', '^dim_'] },
      ],
    },
    ...overrides,
  } as HealthData
}

describe('complexityExplanation', () => {
  it('lists the project’s actual thresholds', () => {
    expect(complexityExplanation(makeHealth()).rules).toEqual([
      'More than 200 lines of SQL',
      'More than 8 joins',
      'More than 10 CTEs',
      'More than 5 subqueries',
    ])
  })

  it('uses custom thresholds rather than the defaults', () => {
    const health = makeHealth({
      config: {
        ...makeHealth().config!,
        complexity_thresholds: {
          high_sql_lines: 50, high_join_count: 3,
          high_cte_count: 4, high_subquery_count: 2,
        },
      },
    })
    expect(complexityExplanation(health).rules?.[0]).toBe('More than 50 lines of SQL')
    expect(complexityExplanation(health).rules?.[1]).toBe('More than 3 joins')
  })

  it('states that exceeding any single threshold is enough', () => {
    expect(complexityExplanation(makeHealth()).summary).toContain('any one')
  })

  it('omits specifics when the payload predates the config field', () => {
    const health = makeHealth({ config: undefined })
    expect(complexityExplanation(health).rules).toBeUndefined()
  })
})

describe('namingExplanation', () => {
  it('spells out the pattern required for each layer', () => {
    expect(namingExplanation(makeHealth()).rules).toEqual([
      'Models in a `staging` folder must match `^stg_`',
      'Models in a `intermediate` folder must match `^int_`',
      'Models in a `marts` folder must match `^fct_` or `^dim_`',
    ])
  })

  it('discloses models skipped because no layer matched', () => {
    expect(namingExplanation(makeHealth()).scope).toBe(
      '17 of 83 models were checked. 66 sit in folders that match no configured ' +
      'layer and were skipped. The score reflects only the models checked.',
    )
  })

  it('does not claim skipped models when everything was checked', () => {
    const health = makeHealth({
      naming: {
        total_checked: 83, total_models: 83, compliant_count: 83,
        compliance_rate: 1, violations: [],
      },
    })
    expect(namingExplanation(health).scope).not.toContain('skipped')
  })

  it('falls back gracefully when total_models is absent', () => {
    const health = makeHealth({
      naming: {
        total_checked: 17, compliant_count: 17, compliance_rate: 1, violations: [],
      },
    })
    expect(namingExplanation(health).scope).toContain('17 models were checked')
  })
})

describe('orphansExplanation', () => {
  it('parenthesises the definition rather than using a dash', () => {
    expect(orphansExplanation(makeHealth()).summary).toBe(
      'A model is an orphan when nothing downstream consumes it (i.e. no other ' +
      'model refs it and no exposure depends on it). Worth 10% of the overall grade.',
    )
  })

  it('closes the parenthesis when no weight is available', () => {
    const health = makeHealth({ config: undefined })
    expect(orphansExplanation(health).summary).toBe(
      'A model is an orphan when nothing downstream consumes it (i.e. no other ' +
      'model refs it and no exposure depends on it).',
    )
  })
})

describe('overallExplanation', () => {
  it('lists the weights behind the grade', () => {
    expect(overallExplanation(makeHealth()).rules).toContain('Documentation — 25%')
    expect(overallExplanation(makeHealth()).rules).toContain('Orphans — 10%')
  })

  it('marks freshness as redistributed when it was excluded', () => {
    const freshness = overallExplanation(makeHealth()).rules?.find(r => r.startsWith('Freshness'))
    expect(freshness).toContain('redistributed')
  })

  it('shows freshness as a normal weight when sources are monitored', () => {
    const health = makeHealth()
    const monitored = {
      ...health,
      score: { ...health.score, freshness_included: true, freshness: 92 },
    } as HealthData
    const freshness = overallExplanation(monitored).rules?.find(r => r.startsWith('Freshness'))
    expect(freshness).toBe('Freshness — 15%')
  })
})

describe('explanationFor', () => {
  it('covers every tab on the health page', () => {
    const tabs = ['overview', 'documentation', 'testing', 'complexity', 'naming', 'orphans']
    for (const tab of tabs) {
      expect(explanationFor(tab, makeHealth()), `missing explanation for ${tab}`).not.toBeNull()
    }
  })

  it('returns null for an unknown tab', () => {
    expect(explanationFor('nope', makeHealth())).toBeNull()
  })
})
