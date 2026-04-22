/**
 * Types for the Docglow site data structure (docglow-data.json).
 * This is the root shape consumed by the frontend React SPA.
 */

import type { ArtifactVersions, ColumnLineageData } from "./artifacts.js";
import type { HealthData } from "./health.js";
import type { LineageData, SearchEntry } from "./lineage.js";
import type { DocglowExposure, DocglowMetric, DocglowModel, DocglowSource } from "./models.js";

export interface HostedFeatures {
  readonly ai_chat: boolean;
  readonly health_history: boolean;
  readonly notifications: boolean;
  readonly description_editing: boolean;
  readonly max_viewers: number;
}

export interface DocglowMetadata {
  readonly generated_at: string;
  readonly docglow_version: string;
  readonly dbt_version: string;
  readonly project_name: string;
  readonly project_id: string;
  readonly target_name: string;
  readonly artifact_versions: ArtifactVersions;
  readonly profiling_enabled: boolean;
  readonly ai_enabled: boolean;
  readonly hosted: boolean;
  readonly workspace_slug: string | null;
  readonly project_slug: string | null;
  readonly api_base_url: string | null;
  readonly published_at: string | null;
  readonly features: HostedFeatures | null;
}

export type LineageBadgeAbbreviation = "smart" | "truncate" | "middle" | "none";

export interface LineageBadgeConfig {
  readonly abbreviation: LineageBadgeAbbreviation;
  readonly max_model_chars: number;
  readonly max_column_chars: number;
}

export interface UiConfig {
  readonly lineage_badge: LineageBadgeConfig;
}

export interface DocglowData {
  readonly metadata: DocglowMetadata;
  readonly models: Record<string, DocglowModel>;
  readonly sources: Record<string, DocglowSource>;
  readonly seeds: Record<string, DocglowModel>;
  readonly snapshots: Record<string, DocglowModel>;
  readonly exposures: Record<string, DocglowExposure>;
  readonly metrics: Record<string, DocglowMetric>;
  readonly lineage: LineageData;
  readonly column_lineage?: ColumnLineageData;
  readonly health: HealthData;
  readonly search_index: SearchEntry[];
  readonly ai_context: AiContext | null;
  readonly ai_key: string | null;
  readonly ui?: UiConfig;
}

// -- AI context (embedded in site data for local AI chat) --------------------

export interface AiContext {
  readonly project_name: string;
  readonly dbt_version: string;
  readonly total_models: number;
  readonly total_sources: number;
  readonly total_seeds: number;
  readonly models: AiCompactModel[];
  readonly seeds: AiCompactModel[];
  readonly sources: AiCompactSource[];
  readonly health_summary: AiHealthSummary;
}

export interface AiCompactModel {
  readonly name: string;
  readonly description: string;
  readonly materialization: string;
  readonly schema: string;
  readonly tags: string[];
  readonly depends_on: string[];
  readonly referenced_by: string[];
  readonly columns?: string[];
  readonly test_status?: Record<string, number>;
  readonly row_count?: number;
}

export interface AiCompactSource {
  readonly name: string;
  readonly description: string;
  readonly schema: string;
  readonly columns: string[];
  readonly freshness_status?: string;
}

export interface AiHealthSummary {
  readonly overall_score: number;
  readonly grade: string;
  readonly documentation_coverage: number;
  readonly test_coverage: number;
  readonly naming_compliance: number;
  readonly high_complexity_count: number;
  readonly orphan_count: number;
}
