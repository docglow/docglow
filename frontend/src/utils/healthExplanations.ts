/**
 * Plain-language descriptions of what each health dimension measures.
 *
 * Complexity thresholds and naming rules are per-project (`docglow.yml`), so
 * these are built from the effective config carried in the health payload —
 * hardcoded prose would be wrong for any project that customises them. Payloads
 * generated before `health.config` existed fall back to omitting the specifics
 * rather than stating defaults that may not apply.
 */
import type { HealthData, NamingRule } from '../types'

export interface Explanation {
  /** What the dimension measures, in one or two sentences. */
  readonly summary: string
  /** The concrete rules in effect, if the payload carries them. */
  readonly rules?: string[]
  /** How much of the project the check actually applied to. */
  readonly scope?: string
}

const pct = (weight: number | undefined): string =>
  weight === undefined ? '' : `${Math.round(weight * 100)}%`

export function documentationExplanation(health: HealthData): Explanation {
  const w = pct(health.config?.weights.documentation)
  const c = health.coverage
  return {
    summary:
      'A model or column counts as documented when it has a non-empty description ' +
      'in your schema yml. The score is the average of model-level and column-level ' +
      `coverage${w ? `, and is worth ${w} of the overall grade` : ''}.`,
    scope:
      `${c.models_documented.total} models and ${c.columns_documented.total} columns ` +
      '(model columns plus source columns) were checked.',
  }
}

export function testingExplanation(health: HealthData): Explanation {
  const w = pct(health.config?.weights.testing)
  const c = health.coverage
  return {
    summary:
      'A model counts as tested when at least one dbt test references it; a column ' +
      'counts when it has a test declared on it. The score averages model-level and ' +
      `column-level coverage${w ? `, and is worth ${w} of the overall grade` : ''}.`,
    rules: [
      'Tests declared in yml count toward coverage even if the latest run did not execute them — this measures test coverage, not run results.',
      'Source columns are counted in the denominator but cannot currently hold tests, which caps column coverage below 100%.',
    ],
    scope:
      `${c.models_tested.total} models and ${c.columns_tested.total} columns were checked.`,
  }
}

export function freshnessExplanation(health: HealthData): Explanation {
  const w = pct(health.config?.weights.freshness)
  return {
    summary:
      'The share of sources with freshness monitoring that are currently passing, ' +
      'from `dbt source freshness`. A warning counts as half a pass.',
    rules: [
      `When no source has freshness configured the dimension is dropped entirely and its ${w || 'weight'} is redistributed across the others, rather than scoring zero.`,
    ],
  }
}

export function complexityExplanation(health: HealthData): Explanation {
  const w = pct(health.config?.weights.complexity)
  const t = health.config?.complexity_thresholds
  return {
    summary:
      'A model is flagged as high complexity when its compiled SQL exceeds any one ' +
      `of the thresholds below${w ? `. Worth ${w} of the overall grade` : ''}. The score ` +
      'is the share of models that stay under all of them.',
    rules: t
      ? [
          `More than ${t.high_sql_lines} lines of SQL`,
          `More than ${t.high_join_count} joins`,
          `More than ${t.high_cte_count} CTEs`,
          `More than ${t.high_subquery_count} subqueries`,
        ]
      : undefined,
    scope: `${health.complexity.total} models were checked. Thresholds are configurable under \`health.complexity\` in docglow.yml.`,
  }
}

function describeRule(rule: NamingRule): string {
  const patterns = rule.patterns.map(p => `\`${p}\``).join(' or ')
  return `Models in a \`${rule.layer}\` folder must match ${patterns}`
}

export function namingExplanation(health: HealthData): Explanation {
  const w = pct(health.config?.weights.naming)
  const n = health.naming
  const rules = health.config?.naming_rules
  const total = n.total_models
  const skipped = total === undefined ? undefined : total - n.total_checked

  return {
    summary:
      'Model names are checked against a pattern for the layer they live in, ' +
      'detected from the folder path. Only models in a folder matching a ' +
      `configured layer are checked${w ? `. Worth ${w} of the overall grade` : ''}.`,
    rules: rules?.length ? rules.map(describeRule) : undefined,
    scope:
      skipped !== undefined && skipped > 0
        ? `${n.total_checked} of ${total} models were checked. ${skipped} sit in folders that match no configured layer and were skipped — the score reflects only the models checked.`
        : `${n.total_checked} models were checked. Rules are configurable under \`health.naming_rules\` in docglow.yml.`,
  }
}

export function orphansExplanation(health: HealthData): Explanation {
  const w = pct(health.config?.weights.orphans)
  return {
    summary:
      'A model is an orphan when nothing downstream consumes it — no other model ' +
      `refs it and no exposure depends on it${w ? `. Worth ${w} of the overall grade` : ''}.`,
    rules: [
      'Exposures count as consumers, so a mart feeding a dashboard is not an orphan.',
      'Orphans are often dead code, but a model consumed directly by a BI tool will also appear here until you declare an exposure for it.',
    ],
    scope: `${health.complexity.total} models were checked.`,
  }
}

const WEIGHT_LABELS: Record<string, string> = {
  documentation: 'Documentation',
  testing: 'Testing',
  freshness: 'Freshness',
  complexity: 'Complexity',
  naming: 'Naming',
  orphans: 'Orphans',
}

export function overallExplanation(health: HealthData): Explanation {
  const weights = health.config?.weights
  const included = health.score.freshness_included !== false
  return {
    summary:
      'The overall score is a weighted blend of the dimensions below. ' +
      'Grades are A at 90, B at 80, C at 70, D at 60.',
    rules: weights
      ? Object.entries(WEIGHT_LABELS)
          .filter(([key]) => weights[key] !== undefined)
          .map(([key, label]) => {
            const share = pct(weights[key])
            const dropped = key === 'freshness' && !included
            return dropped
              ? `${label} — ${share}, not counted here (no monitored sources), redistributed across the rest`
              : `${label} — ${share}`
          })
      : undefined,
  }
}

export function explanationFor(tab: string, health: HealthData): Explanation | null {
  switch (tab) {
    case 'overview': return overallExplanation(health)
    case 'documentation': return documentationExplanation(health)
    case 'testing': return testingExplanation(health)
    case 'freshness': return freshnessExplanation(health)
    case 'complexity': return complexityExplanation(health)
    case 'naming': return namingExplanation(health)
    case 'orphans': return orphansExplanation(health)
    default: return null
  }
}
