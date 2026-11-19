import { describe, it, expect } from 'vitest'
import {
  failingTestCount,
  testRowHasDetail,
  testsEmptyState,
  testsNavBadge,
} from '../utils/testStatus'
import { statusBgColor, statusColor } from '../utils/colors'
import type { ProjectTest, TestSummary } from '../types'

function makeSummary(by_status: Partial<TestSummary['by_status']>): TestSummary {
  return {
    has_run_results: true,
    generated_at: '2026-03-07T05:25:00Z',
    total: 0,
    by_status: { pass: 0, fail: 0, warn: 0, error: 0, not_run: 0, ...by_status },
    by_severity: { error: 0, warn: 0 },
    by_type: {},
    pass_rate: null,
    resources_tested: 0,
  }
}

function makeTest(overrides: Partial<ProjectTest> = {}): ProjectTest {
  return {
    unique_id: 't1',
    name: 'not_null_orders_id',
    test_type: 'not_null',
    is_generic: true,
    column_name: 'id',
    severity: 'error',
    status: 'pass',
    failures: 0,
    execution_time: 0.01,
    package_name: 'p',
    original_file_path: 'models/orders.yml',
    attached_node: 'model.p.orders',
    references: [],
    ...overrides,
  }
}

describe('failingTestCount', () => {
  it('counts fail + error, excluding warn and pass', () => {
    expect(failingTestCount(makeSummary({ fail: 2, error: 1, warn: 3, pass: 10 }))).toBe(3)
  })

  it('is zero when nothing failed (warns do not count)', () => {
    expect(failingTestCount(makeSummary({ warn: 4, pass: 10 }))).toBe(0)
  })
})

describe('testRowHasDetail', () => {
  it('is true for a failing test that carries a message', () => {
    const t = makeTest({ status: 'fail', failures: 37, message: 'Got 37 results, configured to fail if != 0' })
    expect(testRowHasDetail(t)).toBe(true)
  })

  it('is true for a warn test with a message', () => {
    expect(testRowHasDetail(makeTest({ status: 'warn', message: 'Got 3 results' }))).toBe(true)
  })

  it('is true when only a defining file is known (no message)', () => {
    expect(testRowHasDetail(makeTest({ message: undefined, original_file_path: 'models/orders.yml' }))).toBe(true)
  })

  it('is false when there is nothing to reveal', () => {
    expect(testRowHasDetail(makeTest({ message: undefined, original_file_path: '' }))).toBe(false)
  })
})

describe('status color mapping (fail/warn/error surfaces)', () => {
  it('renders fail and error as danger', () => {
    expect(statusColor('fail')).toContain('danger')
    expect(statusColor('error')).toContain('danger')
    expect(statusBgColor('fail')).toContain('danger')
    expect(statusBgColor('error')).toContain('danger')
  })

  it('renders warn as warning', () => {
    expect(statusColor('warn')).toContain('warning')
    expect(statusBgColor('warn')).toContain('warning')
  })

  it('renders pass as success', () => {
    expect(statusColor('pass')).toContain('success')
    expect(statusBgColor('pass')).toContain('success')
  })
})

describe('testsNavBadge', () => {
  it('shows the failing count when anything failed or errored', () => {
    expect(testsNavBadge({ ...makeSummary({ fail: 2, error: 1, pass: 5 }), total: 8 })).toEqual({
      kind: 'fail',
      count: 3,
    })
  })

  it('shows a check only when tests ran and none failed (warns allowed)', () => {
    expect(testsNavBadge({ ...makeSummary({ pass: 5, warn: 1 }), total: 6 })).toEqual({
      kind: 'pass',
    })
  })

  it('shows nothing when run_results.json is missing, even though tests exist', () => {
    const summary = {
      ...makeSummary({ not_run: 28 }),
      total: 28,
      has_run_results: false,
      pass_rate: null,
    }
    expect(testsNavBadge(summary)).toBeNull()
  })

  it('shows nothing when run results exist but none of these tests ran', () => {
    expect(testsNavBadge({ ...makeSummary({ not_run: 4 }), total: 4 })).toBeNull()
  })

  it('shows nothing for a project with no tests', () => {
    expect(testsNavBadge(makeSummary({}))).toBeNull()
  })
})

describe('testsEmptyState', () => {
  it('flags a payload that predates the Tests page (no tests key) as legacy', () => {
    expect(testsEmptyState(undefined)).toBe('legacy')
  })

  it('reports a project with the key but no tests as none', () => {
    expect(testsEmptyState({ tests: [], summary: makeSummary({}) })).toBe('none')
  })

  it('has no empty state when there are tests', () => {
    expect(testsEmptyState({ tests: [makeTest()], summary: makeSummary({ pass: 1 }) })).toBeNull()
  })
})
