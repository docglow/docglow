/**
 * Types for Docglow's transformed model/source/exposure/metric data.
 * These are the shapes that appear in docglow-data.json and are consumed
 * by both the OSS frontend and the cloud dashboard.
 */

import type { RelationshipSummary } from "./erd.js";

// -- Columns -----------------------------------------------------------------

export interface ColumnInsights {
  readonly role: string | null;
  readonly semantic_type: string | null;
  readonly sql_usage: string[];
  readonly confidence: number;
  readonly generated_description: string | null;
}

export interface DocglowColumn {
  readonly name: string;
  readonly description: string;
  readonly data_type: string;
  readonly meta: Record<string, unknown>;
  readonly tags: string[];
  readonly tests: ColumnTest[];
  readonly profile: ColumnProfile | null;
  readonly insights?: ColumnInsights | null;
}

export interface ColumnTest {
  readonly test_name: string;
  readonly test_type: string;
  readonly status: "pass" | "fail" | "warn" | "error" | "not_run";
  readonly config: Record<string, unknown>;
}

export interface ColumnProfile {
  readonly row_count: number;
  readonly null_count: number;
  readonly null_rate: number;
  readonly distinct_count: number;
  readonly distinct_rate: number;
  readonly is_unique: boolean;
  readonly min?: string | number | null;
  readonly max?: string | number | null;
  readonly mean?: number | null;
  readonly median?: number | null;
  readonly stddev?: number | null;
  readonly min_length?: number | null;
  readonly max_length?: number | null;
  readonly avg_length?: number | null;
  readonly top_values?: TopValue[] | null;
  readonly histogram?: HistogramBin[] | null;
}

export interface TopValue {
  readonly value: string;
  readonly frequency: number;
}

export interface HistogramBin {
  readonly low: number;
  readonly high: number;
  readonly count: number;
}

// -- Test results ------------------------------------------------------------

export interface TestResult {
  readonly test_name: string;
  readonly test_type: string;
  readonly column_name: string | null;
  readonly status: "pass" | "fail" | "warn" | "error" | "not_run";
  readonly execution_time: number;
  readonly failures: number;
  readonly message: string | null;
}

export interface LastRun {
  readonly status: string | null;
  readonly execution_time: number | null;
  readonly completed_at: string | null;
}

export interface CatalogStats {
  readonly row_count: number | null;
  readonly bytes: number | null;
  readonly has_stats: boolean;
}

// -- Models ------------------------------------------------------------------

export interface DocglowModel {
  readonly unique_id: string;
  readonly name: string;
  readonly description: string;
  readonly schema: string;
  /**
   * Database/catalog name. Empty string (`''`) when the dbt adapter does not
   * populate it (e.g. dbt-glue, dbt-spark, dbt-athena). Consumers must handle
   * the empty case — do not concatenate `database.schema` unconditionally.
   * Use `formatFqn` from `frontend/src/utils/formatting.ts` for display.
   */
  readonly database: string;
  readonly materialization: string;
  readonly tags: string[];
  readonly meta: Record<string, unknown>;
  readonly path: string;
  readonly folder: string;
  readonly raw_sql: string;
  readonly compiled_sql: string;
  readonly columns: DocglowColumn[];
  readonly depends_on: string[];
  readonly referenced_by: string[];
  readonly sources_used: string[];
  readonly test_results: TestResult[];
  readonly last_run: LastRun | null;
  readonly catalog_stats: CatalogStats;
  /**
   * Total number of ERD relationships (bidirectional: incoming + outgoing FKs)
   * connecting this model to other models. Omitted entirely when ERD
   * inference is disabled (`--enable-erd` flag not passed).
   */
  readonly relationships_count?: number;
  /**
   * Top partners by edge count (capped at 3, sorted by `edge_count` desc
   * with `partner_unique_id` ascending as tiebreak). Omitted entirely
   * when ERD inference is disabled.
   */
  readonly relationships_summary?: RelationshipSummary[];
}

// -- Sources -----------------------------------------------------------------

export interface DocglowSource {
  readonly unique_id: string;
  readonly name: string;
  readonly source_name: string;
  readonly description: string;
  readonly schema: string;
  /**
   * Database/catalog name. Empty string (`''`) when the dbt adapter does not
   * populate it (e.g. dbt-glue, dbt-spark, dbt-athena). Consumers must handle
   * the empty case — do not concatenate `database.schema` unconditionally.
   * Use `formatFqn` from `frontend/src/utils/formatting.ts` for display.
   */
  readonly database: string;
  readonly columns: DocglowColumn[];
  readonly tags: string[];
  readonly meta: Record<string, unknown>;
  readonly loader: string;
  readonly loaded_at_field: string | null;
  readonly freshness_status: string | null;
  readonly freshness_max_loaded_at: string | null;
  readonly freshness_snapshotted_at: string | null;
}

// -- Exposures & Metrics -----------------------------------------------------

export interface DocglowExposure {
  readonly unique_id: string;
  readonly name: string;
  readonly type: string;
  readonly description: string;
  readonly url: string;
  readonly label: string;
  readonly maturity: string;
  readonly depends_on: string[];
  readonly owner: Record<string, string>;
  readonly tags: string[];
}

export interface DocglowMetric {
  readonly unique_id: string;
  readonly name: string;
  readonly description: string;
  readonly label: string;
  readonly type: string;
  readonly depends_on: string[];
  readonly tags: string[];
  readonly package_name?: string;
  /** Models the metric is built on, resolved through its semantic model. */
  readonly models?: string[];
  /** Input metrics of a derived or ratio metric. */
  readonly input_metrics?: string[];
  readonly semantic_models?: string[];
  readonly definition?: MetricDefinition;
  /** Model columns the metric's measures read. */
  readonly columns?: MetricColumnRef[];
}

export interface MetricColumnRef {
  readonly model: string;
  readonly column: string;
}

export interface MetricMeasureRef {
  readonly name?: string;
  readonly agg?: string;
  readonly expr?: string;
  readonly filter?: string[];
}

export interface MetricInputRef {
  readonly name: string;
  readonly alias?: string;
  readonly offset?: string;
  readonly filter?: string[];
}

export interface MetricConversion {
  readonly base_measure?: string;
  readonly conversion_measure?: string;
  readonly entity?: string;
  readonly calculation?: string;
  readonly window?: string;
}

/** The readable parts of a metric's `type_params`; empty keys are omitted. */
export interface MetricDefinition {
  readonly measure?: MetricMeasureRef;
  readonly numerator?: MetricInputRef;
  readonly denominator?: MetricInputRef;
  readonly metrics?: MetricInputRef[];
  readonly expr?: string;
  readonly window?: string;
  readonly grain_to_date?: string;
  readonly conversion?: MetricConversion;
  readonly filter?: string[];
}

/** Union type for any resource that can be displayed. */
export type DocglowResource = DocglowModel | DocglowSource;
