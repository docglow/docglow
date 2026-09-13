import type { ProjectTest, ProjectTestStatus } from '../types'

export interface TestFilters {
  status: ProjectTestStatus | 'all'
  type: string | 'all'
  query: string
}

export const EMPTY_FILTERS: TestFilters = {
  status: 'all',
  type: 'all',
  query: '',
}

/**
 * Apply the Tests dashboard filters to a test list. Kept pure (no React) so the
 * combining logic can be unit-tested directly. The text query matches the test
 * name, column, and any attached resource name, case-insensitively.
 *
 * Note: filtering is by run *status* (the outcome shown in the tiles/badges),
 * not by configured severity. Those are distinct axes — an error-severity test
 * can still warn at runtime — so mixing them in one filter is intentionally
 * avoided. Severity is surfaced per-row for context only.
 */
export function filterTests(tests: ProjectTest[], filters: TestFilters): ProjectTest[] {
  const q = filters.query.trim().toLowerCase()
  return tests.filter(test => {
    if (filters.status !== 'all' && test.status !== filters.status) return false
    if (filters.type !== 'all' && test.test_type !== filters.type) return false
    if (q) {
      const haystack = [
        test.name,
        test.column_name ?? '',
        ...test.attached.map(a => a.name),
      ]
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(q)) return false
    }
    return true
  })
}
