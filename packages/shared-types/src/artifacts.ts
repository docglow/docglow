/**
 * Types for dbt artifact schemas — manifest.json, catalog.json, run_results.json.
 * These describe the raw dbt output before Docglow transforms it.
 */

// -- Column lineage ----------------------------------------------------------

export interface ColumnLineageDependency {
  readonly source_model: string;
  readonly source_column: string;
  readonly transformation: "passthrough" | "rename" | "aggregated" | "derived" | "unknown" | "direct";
}

export interface ColumnDownstreamDependency {
  readonly target_model: string;
  readonly target_column: string;
  readonly transformation: "passthrough" | "rename" | "aggregated" | "derived" | "unknown" | "direct";
}

export type ColumnLineageData = Record<
  string,
  Record<string, ColumnLineageDependency[]>
>;

export interface ColumnEdge {
  readonly sourceModel: string;
  readonly sourceColumn: string;
  readonly targetModel: string;
  readonly targetColumn: string;
  readonly transformation: "passthrough" | "rename" | "aggregated" | "derived" | "unknown" | "direct";
}

// -- Artifact version metadata -----------------------------------------------

export interface ArtifactVersions {
  readonly manifest: string;
  readonly catalog: string | null;
  readonly run_results: string | null;
  readonly sources: string | null;
}
