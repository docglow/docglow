/**
 * Types shared between the OSS CLI and Docglow Cloud.
 * Plan tiers, billing limits, and publish pipeline types.
 */

// -- Plan tiers --------------------------------------------------------------

export type PlanTier = "free" | "starter" | "team" | "business";

export interface PlanLimits {
  readonly maxProjects: number;
  readonly maxModels: number;
  readonly maxPublishesPerDay: number;
  readonly aiQueriesPerMonth: number;
  readonly healthRetentionDays: number;
  readonly artifactRetentionDays: number;
  readonly maxUploadBytes: number;
  readonly customDomain: boolean;
  readonly slackBot: boolean;
  readonly aiDocGeneration: boolean;
}

export const PLAN_LIMITS: Readonly<Record<PlanTier, PlanLimits>> = {
  free: {
    maxProjects: 1,
    maxModels: 50,
    maxPublishesPerDay: 50,
    aiQueriesPerMonth: 0,
    healthRetentionDays: 0,
    artifactRetentionDays: 90,
    maxUploadBytes: 100 * 1024 * 1024, // 100 MB
    customDomain: false,
    slackBot: false,
    aiDocGeneration: false,
  },
  starter: {
    maxProjects: 1,
    maxModels: Infinity,
    maxPublishesPerDay: 50,
    aiQueriesPerMonth: 100,
    healthRetentionDays: 30,
    artifactRetentionDays: 90,
    maxUploadBytes: 100 * 1024 * 1024,
    customDomain: false,
    slackBot: false,
    aiDocGeneration: false,
  },
  team: {
    maxProjects: 3,
    maxModels: Infinity,
    maxPublishesPerDay: 50,
    aiQueriesPerMonth: 500,
    healthRetentionDays: 90,
    artifactRetentionDays: 365,
    maxUploadBytes: 100 * 1024 * 1024,
    customDomain: true,
    slackBot: true,
    aiDocGeneration: true,
  },
  business: {
    maxProjects: 10,
    maxModels: Infinity,
    maxPublishesPerDay: 50,
    aiQueriesPerMonth: 2000,
    healthRetentionDays: 365,
    artifactRetentionDays: 365,
    maxUploadBytes: 100 * 1024 * 1024,
    customDomain: true,
    slackBot: true,
    aiDocGeneration: true,
  },
} as const;

// -- Publish pipeline --------------------------------------------------------

export type PublishStatus = "processing" | "complete" | "failed";

export interface PublishResult {
  readonly publish_id: string;
  readonly status: PublishStatus;
  readonly status_url: string;
}

export interface PublishStatusResponse {
  readonly status: PublishStatus;
  readonly error_message?: string;
  readonly site_url?: string;
  readonly model_count?: number;
  readonly source_count?: number;
}

// -- Health score thresholds -------------------------------------------------

export type HealthGrade = "A" | "B" | "C" | "D" | "F";

export interface HealthGradeThreshold {
  readonly min: number;
  readonly grade: HealthGrade;
}

export const HEALTH_GRADE_THRESHOLDS: readonly HealthGradeThreshold[] = [
  { min: 90, grade: "A" },
  { min: 80, grade: "B" },
  { min: 70, grade: "C" },
  { min: 60, grade: "D" },
  { min: 0, grade: "F" },
] as const;

/** Derive a letter grade from a numeric health score (0-100). */
export function gradeFromScore(score: number): HealthGrade {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const match = HEALTH_GRADE_THRESHOLDS.find((t) => clamped >= t.min);
  return match?.grade ?? "F";
}
