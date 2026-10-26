/**
 * Re-export all types from @docglow/shared-types.
 *
 * The canonical type definitions live in the @docglow/shared-types npm package
 * (source: /packages/shared-types/ in this repo). This file re-exports them
 * so that existing imports throughout the frontend continue to work unchanged.
 */
export type {
  // Artifacts
  ArtifactVersions,
  ColumnLineageData,

  // Models
  CatalogStats,
  ColumnInsights,
  ColumnProfile,
  ColumnTest,
  DocglowColumn,
  DocglowExposure,
  DocglowMetric,
  DocglowModel,
  DocglowResource,
  DocglowSource,
  HistogramBin,
  LastRun,
  TestResult,
  TopValue,

  // Health
  ComplexityData,
  ComplexityModel,
  CoverageData,
  CoverageMetric,
  HealthData,
  HealthScore,
  NamingData,
  NamingViolation,
  OrphanModel,
  UndocumentedModel,

  // Lineage
  LayerDefinition,
  LineageData,
  LineageEdge,
  LineageNode,
  ResourceType,
  TestStatus,

  // Site data
  AiCompactModel,
  AiCompactSource,
  AiContext,
  AiHealthSummary,
  DocglowData,
  DocglowMetadata,
  HostedFeatures,

  // Cloud
  HealthGrade,
  PlanLimits,
  PlanTier,
  PublishResult,
  PublishStatus,
  PublishStatusResponse,
} from "@docglow/shared-types";

export { gradeFromScore, HEALTH_GRADE_THRESHOLDS, PLAN_LIMITS } from "@docglow/shared-types";

// Types extended with new transformation types (pending @docglow/shared-types v0.2.0)
export type TransformationType = 'direct' | 'derived' | 'aggregated' | 'passthrough' | 'rename' | 'unknown';

export interface ColumnLineageDependency {
  readonly source_model: string;
  readonly source_column: string;
  readonly transformation: TransformationType;
}

export interface ColumnDownstreamDependency {
  readonly target_model: string;
  readonly target_column: string;
  readonly transformation: TransformationType;
}

export interface ColumnEdge {
  readonly sourceModel: string;
  readonly sourceColumn: string;
  readonly targetModel: string;
  readonly targetColumn: string;
  readonly transformation: TransformationType;
}

// SearchEntry extended with fields added after @docglow/shared-types v0.1.0.
// These augmentations will be removed once shared-types is republished.
export type { SearchEntry } from "@docglow/shared-types";
declare module "@docglow/shared-types" {
  interface SearchEntry {
    readonly id: string;
    readonly column_name?: string;
    readonly model_name?: string;
  }

  // UI config added in 0.7.3; will be removed from here once shared-types is republished.
  interface DocglowData {
    readonly ui?: UiConfig;
  }

  // Exposure fields added after v0.1.0; remove once shared-types is republished.
  interface DocglowExposure {
    readonly url: string;
    readonly label: string;
    readonly maturity: string;
  }

  // Added in 0.8.6 (DOC-296). False when no source has freshness monitoring, in
  // which case the dimension is excluded from the weighted score and
  // `freshness` is a placeholder 0. Optional so payloads generated before this
  // field existed still parse; treat `undefined` as true. Remove once
  // shared-types is republished.
  interface HealthScore {
    readonly freshness_included?: boolean;
  }

  // Added in 0.8.6 (DOC-299). The effective scoring rules, so the Health page
  // can explain a score using the project's own thresholds and naming rules
  // rather than hardcoded defaults. Remove once shared-types is republished.
  interface HealthData {
    readonly config?: HealthConfigData;
  }

  interface NamingData {
    readonly total_models?: number;
  }
}

export interface ComplexityThresholds {
  readonly high_sql_lines: number;
  readonly high_join_count: number;
  readonly high_cte_count: number;
  readonly high_subquery_count: number;
}

export interface NamingRule {
  readonly layer: string;
  readonly patterns: string[];
}

export interface HealthConfigData {
  readonly weights: Record<string, number>;
  readonly complexity_thresholds: ComplexityThresholds;
  readonly naming_rules: NamingRule[];
}

export type LineageBadgeAbbreviation = 'smart' | 'truncate' | 'middle' | 'none';

export interface LineageBadgeConfig {
  readonly abbreviation: LineageBadgeAbbreviation;
  readonly max_model_chars: number;
  readonly max_column_chars: number;
}

export interface UiConfig {
  readonly lineage_badge: LineageBadgeConfig;
}

// ERD types added after @docglow/shared-types v0.1.0 (see packages/shared-types/src/erd.ts).
// These local definitions + module augmentations will be removed once shared-types is republished.

export type ErdKind = "one_to_one" | "one_to_many" | "many_to_many" | "inferred";

export type ErdEndpoint =
  | "one_and_only_one"
  | "zero_or_one"
  | "one_or_many"
  | "zero_or_many";

export type ErdInferenceSource = "test" | "meta" | "both";

export type ErdSeverity = "error" | "warn" | "info";

export type ErdStatus = "pass" | "fail" | "warn" | "not_run" | "none";

export interface ErdRelationship {
  readonly id: string;
  readonly from_unique_id: string;
  readonly from_column: string;
  readonly to_unique_id: string;
  readonly to_column: string;
  readonly to_model_name: string;
  readonly kind: ErdKind;
  readonly child_endpoint: ErdEndpoint;
  readonly parent_endpoint: ErdEndpoint;
  readonly inference_source: ErdInferenceSource;
  readonly severity: ErdSeverity;
  readonly status: ErdStatus;
  readonly label: string | null;
  readonly test_unique_id: string | null;
  readonly meta_file_path: string | null;
  readonly is_synthetic: boolean;
  readonly parent_column_exists: boolean;
}

export interface RelationshipSummary {
  readonly partner_unique_id: string;
  readonly edge_count: number;
}

declare module "@docglow/shared-types" {
  interface DocglowData {
    readonly relationships?: ErdRelationship[];
  }

  interface DocglowModel {
    readonly relationships_count?: number;
    readonly relationships_summary?: RelationshipSummary[];
  }
}

// Project-wide test catalog (Tests dashboard). Added in the DOC tests-dashboard
// work; local definitions + augmentation until shared-types is republished.
// Mirrors packages/shared-types/src/tests.ts.

export type ProjectTestStatus = "pass" | "fail" | "warn" | "error" | "not_run";

export type TestSeverity = "error" | "warn";

export interface TestAttachment {
  readonly unique_id: string;
  readonly name: string;
  readonly resource_type: string;
}

export interface ProjectTest {
  readonly unique_id: string;
  readonly name: string;
  readonly test_type: string;
  readonly is_generic: boolean;
  readonly column_name: string | null;
  readonly severity: TestSeverity;
  readonly status: ProjectTestStatus;
  readonly failures: number | null;
  readonly execution_time: number | null;
  readonly message: string | null;
  readonly package_name: string;
  readonly original_file_path: string;
  readonly attached: TestAttachment[];
}

export interface TestSummary {
  readonly has_run_results: boolean;
  readonly generated_at: string;
  readonly total: number;
  readonly by_status: Record<ProjectTestStatus, number>;
  readonly by_severity: Record<TestSeverity, number>;
  readonly by_type: Record<string, number>;
  readonly pass_rate: number | null;
  readonly resources_tested: number;
}

export interface TestsData {
  readonly tests: ProjectTest[];
  readonly summary: TestSummary;
}

declare module "@docglow/shared-types" {
  // Payloads generated before the Tests dashboard shipped have no `tests` key,
  // so it is optional; the page guards with a fallback.
  interface DocglowData {
    readonly tests?: TestsData;
  }
}
