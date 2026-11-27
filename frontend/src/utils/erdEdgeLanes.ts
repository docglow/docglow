/**
 * Lane assignment for ERD relationship edges.
 *
 * `ErdEdge` draws each relationship as an orthogonal H-V-H path: out of the
 * child's FK column, along a vertical segment, into the parent's PK column.
 * Turning every edge at the midpoint of its gap stacked all of a channel's
 * vertical segments on the same x, so edges merged into shared trunks and
 * you could not tell which column went to which table.
 *
 * This module gives every edge in a channel its own vertical lane. A channel
 * is the set of edges spanning the same horizontal gap (same left and right
 * anchor x, e.g. one dagre rank to the next). Within a channel, lanes are
 * ordered so no edge's horizontal run crosses another edge's vertical run
 * whenever such an order exists:
 *
 *   - Edge `a`'s left run sits at `a.leftY` and spans [left, laneX(a)]. It
 *     crosses edge `b`'s vertical when `b` turns left of `a` and `a.leftY`
 *     lies strictly inside `b`'s vertical span, so `a` must turn before `b`.
 *   - Edge `a`'s right run sits at `a.rightY` and spans [laneX(a), right].
 *     It crosses `b`'s vertical when `b` turns right of `a` and `a.rightY`
 *     lies strictly inside `b`'s span, so `b` must turn before `a`.
 *
 * Those constraints are topologically sorted, so a channel gets a
 * crossing-free order whenever one exists. When the constraints form a
 * cycle, a crossing is unavoidable; a local search then trims the count.
 * Ties break on geometry then edge id, so the output depends only on the
 * input coordinates, never on input order.
 *
 * Edges whose two ends sit at the same y draw as a straight line and take
 * no lane. Endpoints shared by two edges (several FKs into one PK column)
 * are not crossings: those runs meet at the shared anchor.
 */

/** Preferred distance between neighbouring lanes, in px. */
export const LANE_SPACING = 14
/**
 * Lanes stay this far inside the gap so they clear the crow's-foot glyphs,
 * which reach `2 * GLYPH_OFFSET` (20 px) plus a 3 px circle past the anchor.
 */
export const LANE_MARGIN = 26

/** Ends closer than this (px) in y count as a straight edge. */
const STRAIGHT_EPSILON = 1
/** Overlap tolerance (px) when testing whether a y sits inside a span. */
const SPAN_EPSILON = 0.5

export interface LaneEdgeInput {
  readonly id: string
  readonly fromX: number
  readonly fromY: number
  readonly toX: number
  readonly toY: number
}

export interface EdgeLane {
  /** 0 = the lane closest to the channel's left side. */
  readonly index: number
  /** Number of lanes in the channel. */
  readonly count: number
}

interface ChannelEdge {
  readonly id: string
  readonly leftY: number
  readonly rightY: number
  readonly top: number
  readonly bottom: number
}

function channelKey(e: LaneEdgeInput): string {
  const left = Math.round(Math.min(e.fromX, e.toX))
  const right = Math.round(Math.max(e.fromX, e.toX))
  return `${left}|${right}`
}

function toChannelEdge(e: LaneEdgeInput): ChannelEdge {
  const leftIsFrom = e.fromX <= e.toX
  const leftY = leftIsFrom ? e.fromY : e.toY
  const rightY = leftIsFrom ? e.toY : e.fromY
  return {
    id: e.id,
    leftY,
    rightY,
    top: Math.min(leftY, rightY),
    bottom: Math.max(leftY, rightY),
  }
}

function strictlyInside(y: number, e: ChannelEdge): boolean {
  return y > e.top + SPAN_EPSILON && y < e.bottom - SPAN_EPSILON
}

function compareEdges(a: ChannelEdge, b: ChannelEdge): number {
  if (a.leftY !== b.leftY) return a.leftY - b.leftY
  if (a.rightY !== b.rightY) return a.rightY - b.rightY
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}

/**
 * Order one channel's edges left-to-right.
 *
 * `cost[i][j]` counts the crossings between edges `i` and `j` when `i` turns
 * left of `j`. A greedy pass (Kahn's algorithm when the constraints are
 * acyclic) places next the edge whose crossings with the still-unplaced
 * edges are fewest, ties going to the smallest by `compareEdges`; that
 * yields a crossing-free order whenever one exists. If crossings remain (a
 * cycle), `reduceCrossings` moves single edges while that strictly lowers
 * the total.
 */
function orderChannel(edges: readonly ChannelEdge[]): readonly ChannelEdge[] {
  const sorted = [...edges].sort(compareEdges)
  const n = sorted.length
  const cost = sorted.map((a) =>
    sorted.map((b) => {
      if (a === b) return 0
      // a's right run spans [laneX(a), right], so it crosses b's vertical.
      const aRight = strictlyInside(a.rightY, b) ? 1 : 0
      // b's left run spans [left, laneX(b)], so it crosses a's vertical.
      const bLeft = strictlyInside(b.leftY, a) ? 1 : 0
      return aRight + bLeft
    }),
  )

  const pending = sorted.map((_, i) =>
    cost[i].reduce((sum, c) => sum + c, 0),
  )
  const placed = new Array<boolean>(n).fill(false)
  const order: number[] = []
  for (let step = 0; step < n; step += 1) {
    let pick = -1
    for (let i = 0; i < n; i += 1) {
      if (placed[i]) continue
      if (pick === -1 || pending[i] < pending[pick]) pick = i
    }
    placed[pick] = true
    order.push(pick)
    for (let i = 0; i < n; i += 1) pending[i] -= cost[i][pick]
  }

  return reduceCrossings(order, cost).map((i) => sorted[i])
}

/**
 * Local search over single-edge moves: take each edge out, reinsert it at
 * the position with the fewest crossings against the others, and keep the
 * move only if it is strictly better. Repeats until no move helps. Every
 * kept move lowers the total, so it terminates, and a crossing-free order
 * is left untouched.
 */
function reduceCrossings(
  initial: readonly number[],
  cost: readonly (readonly number[])[],
): readonly number[] {
  let order = [...initial]
  let improved = true
  while (improved) {
    improved = false
    for (let p = 0; p < order.length; p += 1) {
      const e = order[p]
      const rest = order.filter((_, k) => k !== p)
      // Crossings with the others if `e` is inserted before rest[q].
      let atQ = rest.reduce((sum, o) => sum + cost[e][o], 0)
      let best = atQ
      let bestQ = 0
      let current = p === 0 ? atQ : Number.POSITIVE_INFINITY
      for (let q = 1; q <= rest.length; q += 1) {
        const passed = rest[q - 1]
        atQ += cost[passed][e] - cost[e][passed]
        if (atQ < best) {
          best = atQ
          bestQ = q
        }
        if (q === p) current = atQ
      }
      if (best < current) {
        order = [...rest.slice(0, bestQ), e, ...rest.slice(bestQ)]
        improved = true
      }
    }
  }
  return order
}

/**
 * Assign each non-straight edge a lane within its channel.
 *
 * @param edges - edge anchors in canvas px. Self-loops should be left out.
 * @returns lane per edge id. Straight edges (same y at both ends) and edges
 *   whose ends share an x are absent: they draw at the gap midpoint.
 */
export function assignEdgeLanes(
  edges: readonly LaneEdgeInput[],
): ReadonlyMap<string, EdgeLane> {
  const channels = new Map<string, ChannelEdge[]>()
  for (const e of edges) {
    if (Math.abs(e.fromX - e.toX) < 1) continue
    if (Math.abs(e.fromY - e.toY) < STRAIGHT_EPSILON) continue
    const key = channelKey(e)
    const list = channels.get(key)
    if (list) list.push(toChannelEdge(e))
    else channels.set(key, [toChannelEdge(e)])
  }

  const lanes = new Map<string, EdgeLane>()
  for (const channel of channels.values()) {
    const order = orderChannel(channel)
    order.forEach((e, index) => {
      lanes.set(e.id, { index, count: order.length })
    })
  }
  return lanes
}

/**
 * x of an edge's vertical segment. Lanes are spaced `LANE_SPACING` apart and
 * centred on the gap midpoint, shrinking evenly when the gap (less
 * `LANE_MARGIN` on each side) is too narrow to fit them all.
 */
export function laneX(
  lane: EdgeLane | undefined,
  fromX: number,
  toX: number,
): number {
  const left = Math.min(fromX, toX)
  const right = Math.max(fromX, toX)
  const mid = (left + right) / 2
  if (!lane || lane.count < 2) return mid
  const usable = Math.max(0, right - left - 2 * LANE_MARGIN)
  const spacing = Math.min(LANE_SPACING, usable / (lane.count - 1))
  return mid + (lane.index - (lane.count - 1) / 2) * spacing
}
