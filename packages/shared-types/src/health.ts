/**
 * Types for Docglow health scoring — coverage, complexity, naming, orphans.
 * Used by both the OSS CLI health report and the cloud health dashboard.
 */

export interface HealthData {
  readonly score: HealthScore;
  readonly coverage: CoverageData;
  readonly complexity: ComplexityData;
  readonly naming: NamingData;
  readonly orphans: OrphanModel[];
}

export interface HealthScore {
  readonly overall: number;
  readonly documentation: number;
  readonly testing: number;
  readonly freshness: number;
  readonly complexity: number;
  readonly naming: number;
  readonly orphans: number;
  readonly grade: string;
}

export interface CoverageMetric {
  readonly total: number;
  readonly covered: number;
  readonly rate: number;
}

export interface CoverageData {
  readonly models_documented: CoverageMetric;
  readonly columns_documented: CoverageMetric;
  readonly models_tested: CoverageMetric;
  readonly columns_tested: CoverageMetric;
  readonly by_folder: Record<string, CoverageMetric>;
  readonly undocumented_models: UndocumentedModel[];
  readonly untested_models: UndocumentedModel[];
}

export interface UndocumentedModel {
  readonly unique_id: string;
  readonly name: string;
  readonly folder: string;
  readonly downstream_count: number;
}

export interface ComplexityData {
  readonly high_count: number;
  readonly total: number;
  readonly compliance_rate: number;
  readonly models: ComplexityModel[];
}

export interface ComplexityModel {
  readonly unique_id: string;
  readonly name: string;
  readonly folder: string;
  readonly sql_lines: number;
  readonly join_count: number;
  readonly cte_count: number;
  readonly subquery_count: number;
  readonly downstream_count: number;
  readonly is_high_complexity: boolean;
}

export interface NamingData {
  readonly total_checked: number;
  readonly compliant_count: number;
  readonly compliance_rate: number;
  readonly violations: NamingViolation[];
}

export interface NamingViolation {
  readonly unique_id: string;
  readonly name: string;
  readonly folder: string;
  readonly expected_pattern: string;
  readonly layer: string;
}

export interface OrphanModel {
  readonly unique_id: string;
  readonly name: string;
  readonly folder: string;
}
