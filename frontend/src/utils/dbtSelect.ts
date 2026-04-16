/**
 * Parse dbt model selection syntax and resolve to a set of model unique_ids
 * that should be pinned.
 *
 * Supported syntax:
 *   model_name          — pin that model
 *   +model_name         — pin that model (upstream shown via graph lineage)
 *   model_name+         — pin that model (downstream shown via graph lineage)
 *   +model_name+        — pin that model (both shown via graph lineage)
 *   tag:finance         — pin all models with that tag
 *   stg_*               — glob pattern, pins all matching models
 *
 * Space-separated expressions are unioned:
 *   "+fct_orders dim_customers tag:finance"
 *
 * Note: the +/+ markers are accepted for dbt familiarity but do NOT
 * expand upstream/downstream into separate pins. The pin system's
 * depth/direction controls already handle lineage expansion on the graph.
 * This avoids polluting the pin bar with hundreds of chips for a single
 * `+fct_orders` expression.
 */

import type { LineageNode } from '../types'

export interface DbtSelectResult {
  matched: Set<string>
  errors: string[]
}

function globToRegex(pattern: string): RegExp {
  // Escape regex specials except * which we translate to .*
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*')
  return new RegExp(`^${escaped}$`, 'i')
}

function isGlob(s: string): boolean {
  return s.includes('*')
}

/** Find nodes matching a single selector token (without +/+ markers). */
function matchToken(
  token: string,
  nodes: LineageNode[],
  nodesById: Map<string, LineageNode>,
): string[] {
  // tag:xyz
  if (token.startsWith('tag:')) {
    const tag = token.slice(4).toLowerCase()
    return nodes
      .filter(n => (n.tags ?? []).some(t => t.toLowerCase() === tag))
      .map(n => n.id)
  }

  // glob pattern
  if (isGlob(token)) {
    const regex = globToRegex(token)
    return nodes.filter(n => regex.test(n.name)).map(n => n.id)
  }

  // exact unique_id match
  if (nodesById.has(token)) return [token]

  // exact name match
  const byName = nodes.filter(n => n.name === token)
  if (byName.length > 0) return byName.map(n => n.id)

  // case-insensitive name match (last resort)
  const byNameCi = nodes.filter(n => n.name.toLowerCase() === token.toLowerCase())
  return byNameCi.map(n => n.id)
}

export function resolveDbtSelection(
  expression: string,
  nodes: LineageNode[],
): DbtSelectResult {
  const matched = new Set<string>()
  const errors: string[] = []
  const nodesById = new Map(nodes.map(n => [n.id, n]))

  const tokens = expression.trim().split(/\s+/).filter(Boolean)

  for (const rawToken of tokens) {
    // Strip +/+ markers — accepted for dbt familiarity but don't expand pins
    let token = rawToken
    if (token.startsWith('+')) token = token.slice(1)
    if (token.endsWith('+')) token = token.slice(0, -1)

    if (!token) {
      errors.push(`Empty selector in "${rawToken}"`)
      continue
    }

    const hits = matchToken(token, nodes, nodesById)
    if (hits.length === 0) {
      errors.push(`No matches for "${rawToken}"`)
      continue
    }

    for (const id of hits) matched.add(id)
  }

  return { matched, errors }
}
