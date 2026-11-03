/**
 * Auto-layout for ERD nodes using dagre.
 *
 * v1 shipped a fixed-cell grid (`ROW_SLOT_H = 200`) which overlapped when
 * keys-mode tables grew taller than a cell. v1.1 swaps it for dagre — same
 * library already used by lineage and column-trace layouts. dagre measures
 * actual node heights and arranges nodes by edge direction, so child→parent
 * relationships flow left-to-right and tables don't collide.
 *
 * Determinism: dagre's algorithm is deterministic for a fixed input.
 *
 * Star ordering (#153): when dagre's crossing minimisation has no reason to
 * prefer one order over another — the common case for a star schema, where
 * every edge leaves the same fact table — it keeps the order in which edges
 * were added. Those edges are drawn from the fact table's FK *column rows*,
 * though, so a dimension order that differs from the column order makes the
 * connectors cross. Each edge may therefore carry `fromColumnIndex` (the FK
 * column's position in the child table), and edges leaving the same node are
 * fed to dagre in that order. Only the relative order of edges that share a
 * source node changes; when no edge carries an index the input to dagre —
 * and so the layout — is exactly what it was before.
 *
 * The caller must provide per-node heights. ErdCanvas estimates from
 * keys-mode rendering (the default view); the layout still works when users
 * later toggle to compact/full because user-dragged positions take
 * precedence in the canvas.
 */

import dagre from 'dagre'

/** Width of a rendered table card in px. Imported by ErdNode for its width style. */
export const TABLE_W = 220
/** Height of the table header row in px (used for edge anchor math). */
export const ROW_H_HEAD = 36

/** Horizontal spacing between dagre layers (parent→child gap). */
const RANK_SEP = 120
/** Vertical spacing between sibling nodes within a layer. */
const NODE_SEP = 60
/** Outer canvas margin around the laid-out graph. */
const MARGIN = 40

export interface ErdNodePosition {
  readonly x: number
  readonly y: number
}

export interface ErdLayoutNodeInput {
  readonly uid: string
  readonly height: number
}

export interface ErdLayoutEdgeInput {
  readonly from: string
  readonly to: string
  /**
   * Position of the FK column within the `from` (child) table's column list,
   * when known. Edges leaving the same node are laid out in ascending order
   * of this value so the parent tables line up with the column rows the
   * edges are drawn from. Edges without it keep their relative input order.
   */
  readonly fromColumnIndex?: number
}

/**
 * Reorder edges so that, within each group of edges sharing a `from` node,
 * they appear in ascending `fromColumnIndex` order. Every edge stays in one
 * of the array slots its group already occupied, so edges from different
 * nodes keep their relative order. The sort is stable, and edges without an
 * index sort after indexed ones in their group.
 */
function orderEdgesByFromColumn(
  edges: readonly ErdLayoutEdgeInput[],
): readonly ErdLayoutEdgeInput[] {
  if (!edges.some((e) => e.fromColumnIndex !== undefined)) return edges

  const slotsByFrom = new Map<string, number[]>()
  edges.forEach((e, i) => {
    const slots = slotsByFrom.get(e.from)
    if (slots) slots.push(i)
    else slotsByFrom.set(e.from, [i])
  })

  const rank = (e: ErdLayoutEdgeInput): number =>
    e.fromColumnIndex ?? Number.POSITIVE_INFINITY

  const ordered: ErdLayoutEdgeInput[] = edges.slice()
  for (const slots of slotsByFrom.values()) {
    if (slots.length < 2) continue
    const group = slots
      .map((i) => edges[i])
      .sort((a, b) => {
        const ra = rank(a)
        const rb = rank(b)
        return ra === rb ? 0 : ra < rb ? -1 : 1
      })
    slots.forEach((slot, k) => {
      ordered[slot] = group[k]
    })
  }
  return ordered
}

/**
 * Compute dagre-driven positions for ERD nodes.
 *
 * @param nodes - per-node `{uid, height}` records. Width is fixed at TABLE_W.
 * @param edges - directed `{from, to}` pairs (child → parent for ERDs).
 *   Self-loops and edges referencing missing uids are dropped silently.
 *   Duplicate edges between the same pair are deduplicated for layout.
 *   Edges sharing a `from` node are laid out in `fromColumnIndex` order
 *   when it is given (see the star-ordering note above).
 * @returns map from uid → top-left `{x, y}` in canvas px.
 *   Returned positions are dagre-centered then offset by `-width/2, -height/2`
 *   so they match ReactFlow's top-left coordinate convention.
 */
export function computeErdLayout(
  nodes: readonly ErdLayoutNodeInput[],
  edges: readonly ErdLayoutEdgeInput[],
): Record<string, ErdNodePosition> {
  if (nodes.length === 0) return {}

  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: 'LR',
    nodesep: NODE_SEP,
    ranksep: RANK_SEP,
    marginx: MARGIN,
    marginy: MARGIN,
  })
  g.setDefaultEdgeLabel(() => ({}))

  const heightByUid = new Map<string, number>()
  for (const n of nodes) {
    heightByUid.set(n.uid, n.height)
    g.setNode(n.uid, { width: TABLE_W, height: n.height })
  }

  const seen = new Set<string>()
  for (const e of orderEdgesByFromColumn(edges)) {
    if (e.from === e.to) continue
    if (!heightByUid.has(e.from) || !heightByUid.has(e.to)) continue
    const key = `${e.from}->${e.to}`
    if (seen.has(key)) continue
    seen.add(key)
    g.setEdge(e.from, e.to)
  }

  dagre.layout(g)

  const positions: Record<string, ErdNodePosition> = {}
  for (const n of nodes) {
    const dagreNode = g.node(n.uid)
    if (!dagreNode) continue
    positions[n.uid] = {
      x: dagreNode.x - TABLE_W / 2,
      y: dagreNode.y - n.height / 2,
    }
  }
  return positions
}
