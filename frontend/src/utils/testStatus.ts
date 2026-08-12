import type { ProjectTest, TestSummary } from '../types'

/**
 * Count of tests that broke the build on the last run: hard failures plus
 * errors (a `warn`-severity result is intentionally excluded — it did not
 * fail). Drives the red count on the sidebar Tests badge.
 */
export function failingTestCount(summary: TestSummary): number {
  return summary.by_status.fail + summary.by_status.error
}

/**
 * Whether a test row has anything to reveal when expanded — a failure/warn
 * message from the run, or at least the file it was defined in. Passing tests
 * with no message still expand to show provenance.
 */
export function testRowHasDetail(test: ProjectTest): boolean {
  return Boolean(test.message) || test.original_file_path !== ''
}
