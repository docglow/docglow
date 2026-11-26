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
 * Star ordering (#153): when the relationships form a simple star — one fact
 * table holding FKs to several dimension tables that have no other
 * relationships — the dimensions are stacked top-to-bottom in the order their
 * FK columns appear in the fact table, so the relationship lines don't cross.
 * dagre's crossing minimization leaves a star's leaves in edge-insertion
 * order (every leaf ties on barycenter), so sorting the star's edges by FK
 * column position before handing them to dagre is enough. Any other graph
 * shape gets its edges in caller order, exactly as before.
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
  /** Column names in display order. Used to order a star's dimensions. */
  readonly columns?: readonly string[]
}

export interface ErdLayoutEdgeInput {
  readonly from: string
  readonly to: string
  /** FK column on `from`. Used to order a star's dimensions. */
  readonly fromColumn?: string
}

/**
 * If `edges` form a simple star — every edge leaves the same fact table and
 * no dimension is also a fact — return them sorted by where each FK column
 * sits in the fact table's `columns`. Otherwise return `edges` unchanged.
 *
 * Expects self-loops and dangling edges already removed. A dimension reached
 * by several FK columns sorts by its first one; FK columns missing from the
 * fact's column list sort last. The sort is stable, so ties keep caller order.
 */
function orderStarEdges(
  edges: readonly ErdLayoutEdgeInput[],
  columnsByUid: ReadonlyMap<string, readonly string[]>,
): readonly ErdLayoutEdgeInput[] {
  if (edges.length < 2) return edges
  const fact = edges[0].from
  if (edges.some((e) => e.from !== fact)) return edges

  const factColumns = columnsByUid.get(fact) ?? []
  const firstFkIndex = new Map<string, number>()
  for (const e of edges) {
    const idx = e.fromColumn === undefined ? -1 : factColumns.indexOf(e.fromColumn)
    const pos = idx === -1 ? factColumns.length : idx
    firstFkIndex.set(e.to, Math.min(firstFkIndex.get(e.to) ?? pos, pos))
  }
  if (firstFkIndex.size < 2) return edges

  return [...edges].sort(
    (a, b) => (firstFkIndex.get(a.to) ?? 0) - (firstFkIndex.get(b.to) ?? 0),
  )
}

/**
 * Compute dagre-driven positions for ERD nodes.
 *
 * @param nodes - per-node `{uid, height}` records. Width is fixed at TABLE_W.
 * @param edges - directed `{from, to}` pairs (child → parent for ERDs).
 *   Self-loops and edges referencing missing uids are dropped silently.
 *   Duplicate edges between the same pair are deduplicated for layout.
 *   A simple star is ordered by FK column position (see `orderStarEdges`).
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
  const columnsByUid = new Map<string, readonly string[]>()
  for (const n of nodes) {
    heightByUid.set(n.uid, n.height)
    if (n.columns) columnsByUid.set(n.uid, n.columns)
    g.setNode(n.uid, { width: TABLE_W, height: n.height })
  }

  const layoutEdges = edges.filter(
    (e) => e.from !== e.to && heightByUid.has(e.from) && heightByUid.has(e.to),
  )
  const seen = new Set<string>()
  for (const e of orderStarEdges(layoutEdges, columnsByUid)) {
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
