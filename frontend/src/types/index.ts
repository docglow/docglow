export interface ColumnLineageDependency {
  source_model: string
  source_column: string
  transformation: 'direct' | 'derived' | 'aggregated'
}

export interface ColumnDownstreamDependency {
  target_model: string
  target_column: string
  transformation: 'direct' | 'derived' | 'aggregated'
}

export type ColumnLineageData = Record<string, Record<string, ColumnLineageDependency[]>>

export interface ColumnEdge {
  sourceModel: string
  sourceColumn: string
  targetModel: string
  targetColumn: string
  transformation: 'direct' | 'derived' | 'aggregated'
}

export interface DocglowData {
  metadata: DocglowMetadata
  models: Record<string, DocglowModel>
  sources: Record<string, DocglowSource>
  seeds: Record<string, DocglowModel>
  snapshots: Record<string, DocglowModel>
  exposures: Record<string, DocglowExposure>
  metrics: Record<string, DocglowMetric>
  lineage: LineageData
  column_lineage?: ColumnLineageData
  health: HealthData
  search_index: SearchEntry[]
  ai_context: AiContext | null
  ai_key: string | null
}

export interface DocglowMetadata {
  generated_at: string
  docglow_version: string
  dbt_version: string
  project_name: string
  project_id: string
  target_name: string
  artifact_versions: {
    manifest: string
    catalog: string | null
    run_results: string | null
    sources: string | null
  }
  profiling_enabled: boolean
  ai_enabled: boolean
  hosted: boolean
  workspace_slug: string | null
  project_slug: string | null
  api_base_url: string | null
  published_at: string | null
  features: HostedFeatures | null
}

export interface HostedFeatures {
  ai_chat: boolean
  health_history: boolean
  notifications: boolean
  description_editing: boolean
  max_viewers: number
}

export interface DocglowModel {
  unique_id: string
  name: string
  description: string
  schema: string
  database: string
  materialization: string
  tags: string[]
  meta: Record<string, unknown>
  path: string
  folder: string
  raw_sql: string
  compiled_sql: string
  columns: DocglowColumn[]
  depends_on: string[]
  referenced_by: string[]
  sources_used: string[]
  test_results: TestResult[]
  last_run: LastRun | null
  catalog_stats: CatalogStats
}

export interface ColumnInsights {
  role: string | null
  semantic_type: string | null
  sql_usage: string[]
  confidence: number
  generated_description: string | null
}

export interface DocglowColumn {
  name: string
  description: string
  data_type: string
  meta: Record<string, unknown>
  tags: string[]
  tests: ColumnTest[]
  profile: ColumnProfile | null
  insights?: ColumnInsights | null
}

export interface ColumnTest {
  test_name: string
  test_type: string
  status: 'pass' | 'fail' | 'warn' | 'error' | 'not_run'
  config: Record<string, unknown>
}

export interface ColumnProfile {
  row_count: number
  null_count: number
  null_rate: number
  distinct_count: number
  distinct_rate: number
  is_unique: boolean
  min?: string | number | null
  max?: string | number | null
  mean?: number | null
  median?: number | null
  stddev?: number | null
  min_length?: number | null
  max_length?: number | null
  avg_length?: number | null
  top_values?: TopValue[] | null
  histogram?: HistogramBin[] | null
}

export interface TopValue {
  value: string
  frequency: number
}

export interface HistogramBin {
  low: number
  high: number
  count: number
}

export interface TestResult {
  test_name: string
  test_type: string
  column_name: string | null
  status: 'pass' | 'fail' | 'warn' | 'error' | 'not_run'
  execution_time: number
  failures: number
  message: string | null
}

export interface LastRun {
  status: string | null
  execution_time: number | null
  completed_at: string | null
}

export interface CatalogStats {
  row_count: number | null
  bytes: number | null
  has_stats: boolean
}

export interface DocglowSource {
  unique_id: string
  name: string
  source_name: string
  description: string
  schema: string
  database: string
  columns: DocglowColumn[]
  tags: string[]
  meta: Record<string, unknown>
  loader: string
  loaded_at_field: string | null
  freshness_status: string | null
  freshness_max_loaded_at: string | null
  freshness_snapshotted_at: string | null
}

export interface DocglowExposure {
  unique_id: string
  name: string
  type: string
  description: string
  depends_on: string[]
  owner: Record<string, string>
  tags: string[]
}

export interface DocglowMetric {
  unique_id: string
  name: string
  description: string
  label: string
  type: string
  depends_on: string[]
  tags: string[]
}

export interface LayerDefinition {
  name: string
  rank: number
  color: string
}

export interface LineageData {
  nodes: LineageNode[]
  edges: LineageEdge[]
  layer_config?: LayerDefinition[]
}

export interface LineageNode {
  id: string
  name: string
  resource_type: 'model' | 'source' | 'seed' | 'snapshot' | 'exposure' | 'metric'
  materialization: string
  schema: string
  test_status: 'pass' | 'fail' | 'warn' | 'none'
  has_description: boolean
  folder: string
  tags: string[]
  layer?: number
  layer_auto?: boolean
}

export interface LineageEdge {
  source: string
  target: string
}

export interface SearchEntry {
  unique_id: string
  name: string
  resource_type: string
  description: string
  columns: string
  tags: string
  sql_snippet: string
}

// Health types

export interface HealthData {
  score: HealthScore
  coverage: CoverageData
  complexity: ComplexityData
  naming: NamingData
  orphans: OrphanModel[]
}

export interface HealthScore {
  overall: number
  documentation: number
  testing: number
  freshness: number
  complexity: number
  naming: number
  orphans: number
  grade: string
}

export interface CoverageMetric {
  total: number
  covered: number
  rate: number
}

export interface CoverageData {
  models_documented: CoverageMetric
  columns_documented: CoverageMetric
  models_tested: CoverageMetric
  columns_tested: CoverageMetric
  by_folder: Record<string, CoverageMetric>
  undocumented_models: UndocumentedModel[]
  untested_models: UndocumentedModel[]
}

export interface UndocumentedModel {
  unique_id: string
  name: string
  folder: string
  downstream_count: number
}

export interface ComplexityData {
  high_count: number
  total: number
  compliance_rate: number
  models: ComplexityModel[]
}

export interface ComplexityModel {
  unique_id: string
  name: string
  folder: string
  sql_lines: number
  join_count: number
  cte_count: number
  subquery_count: number
  downstream_count: number
  is_high_complexity: boolean
}

export interface NamingData {
  total_checked: number
  compliant_count: number
  compliance_rate: number
  violations: NamingViolation[]
}

export interface NamingViolation {
  unique_id: string
  name: string
  folder: string
  expected_pattern: string
  layer: string
}

export interface OrphanModel {
  unique_id: string
  name: string
  folder: string
}

// AI types

export interface AiContext {
  project_name: string
  dbt_version: string
  total_models: number
  total_sources: number
  total_seeds: number
  models: AiCompactModel[]
  seeds: AiCompactModel[]
  sources: AiCompactSource[]
  health_summary: AiHealthSummary
}

export interface AiCompactModel {
  name: string
  description: string
  materialization: string
  schema: string
  tags: string[]
  depends_on: string[]
  referenced_by: string[]
  columns?: string[]
  test_status?: Record<string, number>
  row_count?: number
}

export interface AiCompactSource {
  name: string
  description: string
  schema: string
  columns: string[]
  freshness_status?: string
}

export interface AiHealthSummary {
  overall_score: number
  grade: string
  documentation_coverage: number
  test_coverage: number
  naming_compliance: number
  high_complexity_count: number
  orphan_count: number
}

/** Union type for any resource that can be displayed */
export type DocglowResource = DocglowModel | DocglowSource
