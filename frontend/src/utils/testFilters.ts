import type { ProjectTest, ProjectTestStatus } from '../types'
import { testResourceIds } from './testResources'

/** Resolves a resource unique_id to the name the user sees (and searches for). */
export type ResourceNameFn = (uid: string) => string

const idBasename: ResourceNameFn = uid => uid.split('.').pop() ?? uid

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
 * name, column, and the display name of every resource the test touches,
 * case-insensitively. Resource names come from `resourceName` (the page passes
 * a payload-backed resolver) rather than raw unique_ids, so a query like the
 * package name doesn't match every test.
 *
 * Note: filtering is by run *status* (the outcome shown in the tiles/badges),
 * not by configured severity. Those are distinct axes — an error-severity test
 * can still warn at runtime — so mixing them in one filter is intentionally
 * avoided. Severity is surfaced per-row for context only.
 */
export function filterTests(
  tests: ProjectTest[],
  filters: TestFilters,
  resourceName: ResourceNameFn = idBasename,
): ProjectTest[] {
  const q = filters.query.trim().toLowerCase()
  return tests.filter(test => {
    if (filters.status !== 'all' && test.status !== filters.status) return false
    if (filters.type !== 'all' && test.test_type !== filters.type) return false
    if (q) {
      const haystack = [
        test.name,
        test.column_name ?? '',
        ...testResourceIds(test).map(resourceName),
      ]
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(q)) return false
    }
    return true
  })
}
