import { describe, it, expect } from 'vitest'
import { failingTestCount, testRowHasDetail } from '../utils/testStatus'
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
    message: null,
    package_name: 'p',
    original_file_path: 'models/orders.yml',
    attached: [{ unique_id: 'model.p.orders', name: 'orders', resource_type: 'model' }],
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
    expect(testRowHasDetail(makeTest({ message: null, original_file_path: 'models/orders.yml' }))).toBe(true)
  })

  it('is false when there is nothing to reveal', () => {
    expect(testRowHasDetail(makeTest({ message: null, original_file_path: '' }))).toBe(false)
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
