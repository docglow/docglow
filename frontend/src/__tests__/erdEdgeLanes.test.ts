import { describe, it, expect } from 'vitest'
import {
  assignEdgeLanes,
  laneX,
  LANE_MARGIN,
  LANE_SPACING,
  type EdgeLane,
  type LaneEdgeInput,
} from '../utils/erdEdgeLanes'

// Star geometry from the #153 fixture after #183's ordering: the fact table
// on the left exits five FK rows on its right side (x = 260); five
// dimensions sit one rank to the right (x = 380), stacked in FK order.
const FACT_RIGHT = 260
const DIM_LEFT = 380
const STAR: readonly LaneEdgeInput[] = [
  { id: 'platform', fromX: FACT_RIGHT, fromY: 300, toX: DIM_LEFT, toY: 60 },
  { id: 'shop', fromX: FACT_RIGHT, fromY: 322, toX: DIM_LEFT, toY: 180 },
  { id: 'staat', fromX: FACT_RIGHT, fromY: 344, toX: DIM_LEFT, toY: 300 },
  { id: 'kalender', fromX: FACT_RIGHT, fromY: 366, toX: DIM_LEFT, toY: 420 },
  { id: 'artikel', fromX: FACT_RIGHT, fromY: 388, toX: DIM_LEFT, toY: 540 },
]

interface Segment {
  readonly id: string
  readonly x1: number
  readonly x2: number
  readonly y1: number
  readonly y2: number
}

/** The H-V-H path ErdEdge draws, as its two horizontal and one vertical runs. */
function route(e: LaneEdgeInput, lane: EdgeLane | undefined) {
  const x = laneX(lane, e.fromX, e.toX)
  const h = (y: number, xa: number, xb: number): Segment => ({
    id: e.id,
    x1: Math.min(xa, xb),
    x2: Math.max(xa, xb),
    y1: y,
    y2: y,
  })
  return {
    horizontals: [h(e.fromY, e.fromX, x), h(e.toY, x, e.toX)],
    vertical: {
      id: e.id,
      x1: x,
      x2: x,
      y1: Math.min(e.fromY, e.toY),
      y2: Math.max(e.fromY, e.toY),
    },
  }
}

function routeAll(
  edges: readonly LaneEdgeInput[],
  lanes: ReadonlyMap<string, EdgeLane> = assignEdgeLanes(edges),
) {
  return edges.map((e) => route(e, lanes.get(e.id)))
}

function permutations(items: readonly number[]): number[][] {
  if (items.length <= 1) return [[...items]]
  return items.flatMap((item, i) =>
    permutations([...items.slice(0, i), ...items.slice(i + 1)]).map((rest) => [
      item,
      ...rest,
    ]),
  )
}

/** Proper crossings: a horizontal run passing through the interior of
 *  another edge's vertical run. Touching at an endpoint doesn't count. */
function countCrossings(
  edges: readonly LaneEdgeInput[],
  lanes?: ReadonlyMap<string, EdgeLane>,
): number {
  const routes = routeAll(edges, lanes)
  let count = 0
  for (const a of routes) {
    for (const b of routes) {
      if (a === b) continue
      const v = b.vertical
      for (const h of a.horizontals) {
        if (
          h.x1 < v.x1 - 1e-6 &&
          h.x2 > v.x1 + 1e-6 &&
          h.y1 > v.y1 + 1e-6 &&
          h.y1 < v.y2 - 1e-6
        ) {
          count += 1
        }
      }
    }
  }
  return count
}

/** Pairs of edges whose vertical runs overlap on the same x. */
function sharedVerticals(edges: readonly LaneEdgeInput[]): string[] {
  const verticals = routeAll(edges)
    .map((r) => r.vertical)
    .filter((v) => v.y2 - v.y1 > 1e-6)
  const shared: string[] = []
  for (let i = 0; i < verticals.length; i += 1) {
    for (let j = i + 1; j < verticals.length; j += 1) {
      const a = verticals[i]
      const b = verticals[j]
      if (Math.abs(a.x1 - b.x1) < 1e-6 && a.y1 < b.y2 && b.y1 < a.y2) {
        shared.push(`${a.id}/${b.id}`)
      }
    }
  }
  return shared
}

/** Deterministic pseudo-random generator (mulberry32). */
function rng(seed: number): () => number {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function shuffled<T>(items: readonly T[], seed: number): T[] {
  const next = rng(seed)
  const out = [...items]
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(next() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

describe('assignEdgeLanes', () => {
  it('returns no lanes for no edges', () => {
    expect(assignEdgeLanes([]).size).toBe(0)
  })

  it('gives every bent edge in the star its own lane', () => {
    const lanes = assignEdgeLanes(STAR)
    const bent = STAR.filter((e) => e.fromY !== e.toY)
    expect(lanes.size).toBe(bent.length)
    const indices = bent.map((e) => lanes.get(e.id)?.index)
    expect(new Set(indices).size).toBe(bent.length)
    for (const e of bent) expect(lanes.get(e.id)?.count).toBe(bent.length)
  })

  it('leaves no two star edges sharing a vertical segment', () => {
    expect(sharedVerticals(STAR)).toEqual([])
  })

  it('routes the star without crossings', () => {
    expect(countCrossings(STAR)).toBe(0)
  })

  it('nests edges to dimensions above the fact so they turn top-first', () => {
    // platform (top-most dimension) turns closest to the fact, then shop,
    // then staat: any other order drives a lower edge's run across a
    // higher edge's vertical.
    const lanes = assignEdgeLanes(STAR)
    const x = (id: string) => {
      const e = STAR.find((s) => s.id === id)!
      return laneX(lanes.get(id), e.fromX, e.toX)
    }
    expect(x('platform')).toBeLessThan(x('shop'))
    expect(x('shop')).toBeLessThan(x('staat'))
  })

  it('nests edges to dimensions below the fact so they turn bottom-first', () => {
    const below: LaneEdgeInput[] = [
      { id: 'a', fromX: 0, fromY: 0, toX: 200, toY: 100 },
      { id: 'b', fromX: 0, fromY: 22, toX: 200, toY: 200 },
      { id: 'c', fromX: 0, fromY: 44, toX: 200, toY: 300 },
    ]
    const lanes = assignEdgeLanes(below)
    expect(lanes.get('c')!.index).toBeLessThan(lanes.get('b')!.index)
    expect(lanes.get('b')!.index).toBeLessThan(lanes.get('a')!.index)
    expect(countCrossings(below)).toBe(0)
  })

  it('gives a straight edge no lane', () => {
    const lanes = assignEdgeLanes([
      { id: 'flat', fromX: 0, fromY: 50, toX: 200, toY: 50 },
      { id: 'bent', fromX: 0, fromY: 50, toX: 200, toY: 120 },
    ])
    expect(lanes.has('flat')).toBe(false)
    expect(lanes.get('bent')).toEqual({ index: 0, count: 1 })
  })

  it('assigns lanes per channel (shared left and right x)', () => {
    const edges: LaneEdgeInput[] = [
      { id: 'r1a', fromX: 0, fromY: 0, toX: 200, toY: 100 },
      { id: 'r1b', fromX: 0, fromY: 30, toX: 200, toY: 200 },
      { id: 'r2a', fromX: 400, fromY: 0, toX: 600, toY: 100 },
    ]
    const lanes = assignEdgeLanes(edges)
    expect(lanes.get('r1a')?.count).toBe(2)
    expect(lanes.get('r1b')?.count).toBe(2)
    expect(lanes.get('r2a')).toEqual({ index: 0, count: 1 })
  })

  it('treats a right-to-left edge by its left and right ends', () => {
    // Same geometry as the downward nest, but drawn from the right-hand
    // table back to the left: lanes depend on the gap, not edge direction.
    const ltr: LaneEdgeInput[] = [
      { id: 'a', fromX: 0, fromY: 0, toX: 200, toY: 100 },
      { id: 'b', fromX: 0, fromY: 22, toX: 200, toY: 200 },
    ]
    const rtl = ltr.map((e) => ({
      id: e.id,
      fromX: e.toX,
      fromY: e.toY,
      toX: e.fromX,
      toY: e.fromY,
    }))
    expect(assignEdgeLanes(rtl)).toEqual(assignEdgeLanes(ltr))
  })

  it('separates parallel edges into the same PK column without crossings', () => {
    // Two FKs on one child pointing at the same parent column.
    const edges: LaneEdgeInput[] = [
      { id: 'customer', fromX: 0, fromY: 122, toX: 200, toY: 50 },
      { id: 'referrer', fromX: 0, fromY: 100, toX: 200, toY: 50 },
    ]
    expect(sharedVerticals(edges)).toEqual([])
    expect(countCrossings(edges)).toBe(0)
  })

  it('is deterministic regardless of input order', () => {
    const expected = assignEdgeLanes(STAR)
    for (let seed = 1; seed <= 20; seed += 1) {
      expect(assignEdgeLanes(shuffled(STAR, seed))).toEqual(expected)
    }
  })

  it('stays deterministic and distinct when a crossing is unavoidable', () => {
    // `inner` sits wholly inside `outer`'s span, so whichever side it turns
    // on, one of its runs crosses `outer`'s vertical.
    const edges: LaneEdgeInput[] = [
      { id: 'outer', fromX: 0, fromY: 0, toX: 200, toY: 300 },
      { id: 'inner', fromX: 0, fromY: 200, toX: 200, toY: 100 },
    ]
    const lanes = assignEdgeLanes(edges)
    expect(lanes.get('outer')!.index).not.toBe(lanes.get('inner')!.index)
    expect(assignEdgeLanes([...edges].reverse())).toEqual(lanes)
    expect(sharedVerticals(edges)).toEqual([])
  })

  it('routes any crossing-free star without crossings or shared verticals', () => {
    // Random stars: k dimensions stacked in FK-column order (as #183 lays
    // them out), fact rows 22 px apart, dimensions anywhere in y order.
    for (let seed = 1; seed <= 200; seed += 1) {
      const next = rng(seed)
      const k = 2 + Math.floor(next() * 9)
      const factTop = Math.floor(next() * 400)
      const dimYs = Array.from({ length: k }, () => Math.floor(next() * 1200)).sort(
        (a, b) => a - b,
      )
      const edges: LaneEdgeInput[] = dimYs.map((toY, i) => ({
        id: `dim${i}`,
        fromX: 0,
        fromY: factTop + i * 22,
        toX: 120,
        toY,
      }))
      expect(countCrossings(edges), `seed ${seed}`).toBe(0)
      expect(sharedVerticals(edges), `seed ${seed}`).toEqual([])
      expect(assignEdgeLanes(shuffled(edges, seed))).toEqual(assignEdgeLanes(edges))
    }
  })

  it('reaches the fewest possible crossings on small random channels', () => {
    // Arbitrary channels (several sources, shared targets, mixed
    // directions): brute-force every lane order. Lanes must be crossing-free
    // whenever some order is, and match the minimum when crossings are
    // unavoidable.
    for (let seed = 1; seed <= 150; seed += 1) {
      const next = rng(seed)
      const n = 2 + Math.floor(next() * 5)
      const edges: LaneEdgeInput[] = Array.from({ length: n }, (_, i) => ({
        id: `e${i}`,
        fromX: 0,
        fromY: Math.floor(next() * 10) * 22,
        toX: 120,
        toY: Math.floor(next() * 10) * 22 + 11,
      }))
      const best = Math.min(
        ...permutations(edges.map((_, i) => i)).map((order) => {
          const lanes = new Map<string, EdgeLane>()
          order.forEach((edgeIndex, index) =>
            lanes.set(edges[edgeIndex].id, { index, count: n }),
          )
          return countCrossings(edges, lanes)
        }),
      )
      expect(sharedVerticals(edges), `seed ${seed}`).toEqual([])
      expect(countCrossings(edges), `seed ${seed}`).toBe(best)
    }
  })
})

describe('laneX', () => {
  it('turns at the gap midpoint without a lane or with a single lane', () => {
    expect(laneX(undefined, 0, 120)).toBe(60)
    expect(laneX({ index: 0, count: 1 }, 0, 120)).toBe(60)
  })

  it('spaces lanes LANE_SPACING apart, centred on the midpoint', () => {
    const xs = [0, 1, 2].map((index) => laneX({ index, count: 3 }, 0, 120))
    expect(xs).toEqual([60 - LANE_SPACING, 60, 60 + LANE_SPACING])
  })

  it('shrinks spacing to keep lanes clear of the crow’s-foot glyphs', () => {
    const count = 20
    const xs = Array.from({ length: count }, (_, index) =>
      laneX({ index, count }, 0, 120),
    )
    expect(xs[0]).toBeCloseTo(LANE_MARGIN)
    expect(xs[count - 1]).toBeCloseTo(120 - LANE_MARGIN)
    expect(new Set(xs).size).toBe(count)
  })

  it('orders lanes left to right whichever way the edge runs', () => {
    expect(laneX({ index: 0, count: 2 }, 120, 0)).toBeLessThan(
      laneX({ index: 1, count: 2 }, 120, 0),
    )
  })
})
