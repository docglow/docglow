/**
 * Types for Docglow's project-wide test catalog (the Tests dashboard).
 *
 * Built solely from the local project's manifest.json and (optionally)
 * run_results.json. This is a single point-in-time snapshot of the most recent
 * `dbt test` / `dbt build` — there is no run history or warehouse persistence.
 */

/** Normalized outcome of a single test's latest run. */
export type ProjectTestStatus = "pass" | "fail" | "warn" | "error" | "not_run";

/** Configured severity of a test (dbt `config.severity`). */
export type TestSeverity = "error" | "warn";

/**
 * A single dbt test with its definition and latest result.
 *
 * Optional fields are omitted from the payload (not sent as `null` / `[]`)
 * when empty, to keep the payload proportional to what each test says.
 */
export interface ProjectTest {
  readonly unique_id: string;
  readonly name: string;
  /** Generic test name (e.g. `not_null`) or `"singular"` for data tests. */
  readonly test_type: string;
  readonly is_generic: boolean;
  /** Absent for tests not defined on a column. */
  readonly column_name?: string;
  readonly severity: TestSeverity;
  readonly status: ProjectTestStatus;
  /** Failing row count from the last run; absent when the test has not run. */
  readonly failures?: number;
  /** Seconds; absent when the test has not run. */
  readonly execution_time?: number;
  /** dbt's result message; absent when there is none (e.g. every pass). */
  readonly message?: string;
  readonly package_name: string;
  readonly original_file_path: string;
  /**
   * unique_id of the resource the test is defined on — dbt's `attached_node`.
   * Absent for singular tests, which dbt attaches to no single resource.
   * Resolve names via the payload's models/seeds/snapshots/sources maps.
   */
  readonly attached_node?: string;
  /**
   * Other model/source/seed/snapshot unique_ids the test reads, excluding
   * `attached_node`: the referenced model of a `relationships` test, or every
   * resource of a singular test. Absent when there are none.
   */
  readonly references?: string[];
}

/** Aggregate rollup across every test in the project. */
export interface TestSummary {
  /** Whether a run_results.json was loaded at all. */
  readonly has_run_results: boolean;
  /** `generated_at` of the run_results artifact (empty when absent). */
  readonly generated_at: string;
  readonly total: number;
  readonly by_status: Record<ProjectTestStatus, number>;
  readonly by_severity: Record<TestSeverity, number>;
  /** Count per generic test type, sorted most-common first. */
  readonly by_type: Record<string, number>;
  /**
   * Fraction of tests that ran and did not fail (warn counts as a pass).
   * `null` when nothing ran, so consumers never render a misleading 0%/100%.
   */
  readonly pass_rate: number | null;
  /** Distinct models/sources covered by at least one test. */
  readonly resources_tested: number;
}

/** The `tests` key of docglow-data.json. */
export interface TestsData {
  readonly tests: ProjectTest[];
  readonly summary: TestSummary;
}
