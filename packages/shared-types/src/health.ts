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
  /**
   * The rules these scores were produced under. Complexity thresholds and
   * naming rules are overridable per project in docglow.yml, so anything that
   * explains a score must read them from here rather than assume defaults.
   * Optional for payloads generated before this field existed.
   */
  readonly config?: HealthConfigData;
}

export interface HealthConfigData {
  readonly weights: Record<string, number>;
  readonly complexity_thresholds: ComplexityThresholds;
  readonly naming_rules: NamingRule[];
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

export interface HealthScore {
  readonly overall: number;
  readonly documentation: number;
  readonly testing: number;
  /** Meaningless when `freshness_included` is false — do not render as a score. */
  readonly freshness: number;
  readonly complexity: number;
  readonly naming: number;
  readonly orphans: number;
  readonly grade: string;
  /**
   * False when no source has freshness monitoring configured, in which case the
   * dimension is excluded from the weighted score and `freshness` is a
   * placeholder 0. Optional so payloads generated before this field existed
   * still parse; treat `undefined` as true.
   */
  readonly freshness_included?: boolean;
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
  /**
   * Every model considered, including those whose folder matched no configured
   * layer and were therefore never checked. `total_checked` alone hides that a
   * score may come from a fraction of the project.
   */
  readonly total_models?: number;
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
