import type { DocglowData, ProjectTest } from '../types'
import { buildResourcePath } from './resourceRoutes'

/** The resource maps a test's unique_ids resolve against. */
export type ResourceMaps = Pick<DocglowData, 'models' | 'seeds' | 'snapshots' | 'sources'>

export interface ResolvedResource {
  readonly uid: string
  readonly name: string
  /** SPA route, or null when the resource is not in this payload (render as text). */
  readonly path: string | null
}

/**
 * Resolve a model/seed/snapshot/source unique_id to its display name and page.
 * An id missing from the payload falls back to its trailing segment with no
 * path, so the UI never links to a page that was not generated.
 */
export function resolveResource(uid: string, data: ResourceMaps): ResolvedResource {
  const node = data.models[uid] ?? data.seeds[uid] ?? data.snapshots[uid]
  if (node) return { uid, name: node.name, path: buildResourcePath(uid) }
  const source = data.sources[uid]
  if (source) {
    const name = source.source_name ? `${source.source_name}.${source.name}` : source.name
    return { uid, name, path: buildResourcePath(uid) }
  }
  return { uid, name: uid.split('.').pop() ?? uid, path: null }
}

/** Every resource a test touches: the attached node first, then its references. */
export function testResourceIds(test: ProjectTest): string[] {
  const refs = test.references ?? []
  return test.attached_node ? [test.attached_node, ...refs] : [...refs]
}

/**
 * What the table's Resource cell shows.
 *
 * - `single`: the resource the test is defined on (dbt's `attached_node`), or the
 *   only resource a singular test reads.
 * - `many`: a singular test reading several resources. dbt assigns singular
 *   tests no attached node, so no resource is promoted to primary; the cell
 *   reads "N resources" and the drill-down lists them all.
 */
export type ResourceCell =
  | { readonly kind: 'single'; readonly uid: string }
  | { readonly kind: 'many'; readonly uids: string[] }
  | { readonly kind: 'none' }

export function resourceCell(test: ProjectTest): ResourceCell {
  if (test.attached_node) return { kind: 'single', uid: test.attached_node }
  const refs = test.references ?? []
  const [only, ...rest] = refs
  if (only === undefined) return { kind: 'none' }
  if (rest.length === 0) return { kind: 'single', uid: only }
  return { kind: 'many', uids: refs }
}
