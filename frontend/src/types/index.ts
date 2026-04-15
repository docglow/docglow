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
}
