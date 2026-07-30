/**
 * The project's shape as a left-to-right flow of layers.
 *
 * "How is this project organized?" is the question a newcomer actually arrives
 * with, and it is the one `dbt docs` has never answered. The lineage graph
 * already carries the answer — every node is assigned a layer rank — so this
 * reduces that to counts per layer without re-deriving anything.
 */
import type { DocglowData, LayerDefinition, LineageNode } from '../types'

export interface LayerSegment {
  readonly rank: number
  readonly name: string
  readonly label: string
  readonly color: string
  readonly count: number
}

const FALLBACK_COLOR = '#e2e8f0'

function titleCase(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** Count nodes per layer rank. Nodes with no layer are not part of the flow. */
function countsByRank(nodes: readonly LineageNode[]): Map<number, number> {
  const counts = new Map<number, number>()
  for (const node of nodes) {
    if (node.layer == null) continue
    counts.set(node.layer, (counts.get(node.layer) ?? 0) + 1)
  }
  return counts
}

/**
 * Layer definitions to render, in rank order.
 *
 * Falls back to synthesising definitions from the ranks present on nodes, so a
 * project whose payload predates layer_config still gets a map.
 */
function definitionsFor(
  configured: readonly LayerDefinition[] | undefined,
  counts: Map<number, number>,
): LayerDefinition[] {
  if (configured?.length) return [...configured]
  return [...counts.keys()]
    .sort((a, b) => a - b)
    .map(rank => ({ name: `Layer ${rank}`, rank, color: FALLBACK_COLOR }))
}

/**
 * The populated layers of a project, in flow order.
 *
 * Empty layers are dropped rather than rendered as zeroes — a project with no
 * exposures should not be shown an "Exposures 0" segment implying it failed to
 * fill one in. Returns an empty array when fewer than two layers are populated,
 * because a single box is not a flow and communicates nothing.
 */
export function buildProjectMap(data: DocglowData): LayerSegment[] {
  const counts = countsByRank(data.lineage.nodes)
  const segments = definitionsFor(data.lineage.layer_config, counts)
    .filter(def => (counts.get(def.rank) ?? 0) > 0)
    .sort((a, b) => a.rank - b.rank)
    .map(def => ({
      rank: def.rank,
      name: def.name,
      label: titleCase(def.name),
      color: def.color || FALLBACK_COLOR,
      count: counts.get(def.rank) ?? 0,
    }))

  return segments.length < 2 ? [] : segments
}

/** The nodes in one layer, name-sorted, for drilling into a segment. */
export function nodesInLayer(data: DocglowData, rank: number): LineageNode[] {
  return data.lineage.nodes
    .filter(node => node.layer === rank)
    .sort((a, b) => a.name.localeCompare(b.name))
}
