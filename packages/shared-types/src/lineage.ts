/**
 * Types for Docglow lineage graph — nodes, edges, and layer configuration.
 */

export type ResourceType =
  | "model"
  | "source"
  | "seed"
  | "snapshot"
  | "exposure"
  | "metric";

export type TestStatus = "pass" | "fail" | "warn" | "none";

export interface LayerDefinition {
  readonly name: string;
  readonly rank: number;
  readonly color: string;
}

export interface LineageData {
  readonly nodes: LineageNode[];
  readonly edges: LineageEdge[];
  readonly layer_config?: LayerDefinition[];
}

export interface LineageNode {
  readonly id: string;
  readonly name: string;
  readonly resource_type: ResourceType;
  readonly materialization: string;
  readonly schema: string;
  readonly test_status: TestStatus;
  readonly has_description: boolean;
  readonly folder: string;
  readonly tags: string[];
  readonly layer?: number;
  readonly layer_auto?: boolean;
}

export interface LineageEdge {
  readonly source: string;
  readonly target: string;
}

export interface SearchEntry {
  readonly unique_id: string;
  readonly name: string;
  readonly resource_type: string;
  readonly description: string;
  readonly columns: string;
  readonly tags: string;
  readonly sql_snippet: string;
  /** Present only on column entries — the column name itself. */
  readonly column_name?: string;
  /** Present only on column entries — the parent model/source name. */
  readonly model_name?: string;
}
