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
  ColumnDownstreamDependency,
  ColumnEdge,
  ColumnLineageData,
  ColumnLineageDependency,

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
  SearchEntry,
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
