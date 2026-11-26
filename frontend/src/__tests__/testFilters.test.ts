import { describe, it, expect } from 'vitest'
import { filterTests, EMPTY_FILTERS, type TestFilters } from '../utils/testFilters'
import type { ProjectTest } from '../types'

function makeTest(overrides: Partial<ProjectTest> = {}): ProjectTest {
  return {
    unique_id: 'test.p.not_null_customers_id.abc',
    name: 'not_null_customers_id',
    test_type: 'not_null',
    is_generic: true,
    column_name: 'id',
    severity: 'error',
    status: 'pass',
    failures: 0,
    execution_time: 0.01,
    package_name: 'p',
    original_file_path: 'models/customers.yml',
    attached_node: 'model.jaffle_shop.customers',
    references: [],
    ...overrides,
  }
}

const tests: ProjectTest[] = [
  makeTest({ unique_id: 't1', name: 'not_null_customers_id', status: 'pass', test_type: 'not_null' }),
  makeTest({
    unique_id: 't2',
    name: 'unique_orders_id',
    status: 'fail',
    test_type: 'unique',
    severity: 'warn',
    column_name: 'order_id',
    attached_node: 'model.jaffle_shop.orders',
  }),
  makeTest({
    unique_id: 't3',
    name: 'assert_positive_revenue',
    status: 'error',
    test_type: 'singular',
    is_generic: false,
    column_name: undefined,
    attached_node: undefined,
    references: ['model.jaffle_shop.revenue'],
  }),
]

describe('filterTests', () => {
  it('returns everything with empty filters', () => {
    expect(filterTests(tests, EMPTY_FILTERS)).toHaveLength(3)
  })

  it('filters by status', () => {
    const out = filterTests(tests, { ...EMPTY_FILTERS, status: 'fail' })
    expect(out.map(t => t.unique_id)).toEqual(['t2'])
  })

  it('filters by type', () => {
    const out = filterTests(tests, { ...EMPTY_FILTERS, type: 'singular' })
    expect(out.map(t => t.unique_id)).toEqual(['t3'])
  })

  it('matches query against name, column, and every resource name (attached + references)', () => {
    expect(filterTests(tests, { ...EMPTY_FILTERS, query: 'orders' }).map(t => t.unique_id)).toEqual(['t2'])
    expect(filterTests(tests, { ...EMPTY_FILTERS, query: 'order_id' }).map(t => t.unique_id)).toEqual(['t2'])
    expect(filterTests(tests, { ...EMPTY_FILTERS, query: 'revenue' }).map(t => t.unique_id)).toEqual(['t3'])
  })

  it('searches resolved resource names, not raw unique_ids', () => {
    // The package name is in every id; it must not match every test.
    expect(filterTests(tests, { ...EMPTY_FILTERS, query: 'jaffle_shop' })).toHaveLength(0)
    // A payload-backed resolver supplies the display name that is searched.
    const names: Record<string, string> = { 'model.jaffle_shop.orders': 'fct_orders' }
    const byName = (uid: string) => names[uid] ?? uid.split('.').pop() ?? uid
    expect(
      filterTests(tests, { ...EMPTY_FILTERS, query: 'fct_' }, byName).map(t => t.unique_id),
    ).toEqual(['t2'])
  })

  it('combines filters (AND semantics)', () => {
    const filters: TestFilters = { status: 'error', type: 'singular', query: 'revenue' }
    expect(filterTests(tests, filters).map(t => t.unique_id)).toEqual(['t3'])
    expect(filterTests(tests, { ...filters, query: 'nope' })).toHaveLength(0)
  })
})
