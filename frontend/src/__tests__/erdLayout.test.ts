import { describe, it, expect } from 'vitest'
import { computeErdLayout, TABLE_W } from '../utils/erdLayout'

const H = 200

const node = (uid: string, height = H) => ({ uid, height })
const edge = (from: string, to: string) => ({ from, to })

/** Two axis-aligned boxes at top-left {x,y} of size (w, h) overlap iff
 *  their open intervals intersect on both axes. Used to assert dagre's
 *  output never produces overlapping nodes. */
function overlaps(
  a: { x: number; y: number; w: number; h: number },
  b: { x: number; y: number; w: number; h: number },
): boolean {
  return (
    a.x < b.x + b.w &&
    a.x + a.w > b.x &&
    a.y < b.y + b.h &&
    a.y + a.h > b.y
  )
}

describe('computeErdLayout (dagre)', () => {
  it('returns empty object for empty input', () => {
    expect(computeErdLayout([], [])).toEqual({})
  })

  it('places a single node at a finite position', () => {
    const result = computeErdLayout([node('m.a')], [])
    expect(result['m.a']).toBeDefined()
    expect(Number.isFinite(result['m.a'].x)).toBe(true)
    expect(Number.isFinite(result['m.a'].y)).toBe(true)
  })

  it('produces non-overlapping rectangles for connected nodes', () => {
    const nodes = [
      node('m.orders'),
      node('m.customers'),
      node('m.items'),
      node('m.products'),
    ]
    const edges = [
      edge('m.orders', 'm.customers'),
      edge('m.items', 'm.orders'),
      edge('m.items', 'm.products'),
    ]
    const result = computeErdLayout(nodes, edges)

    const rects = nodes.map((n) => ({
      uid: n.uid,
      x: result[n.uid].x,
      y: result[n.uid].y,
      w: TABLE_W,
      h: n.height,
    }))

    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        expect(overlaps(rects[i], rects[j])).toBe(false)
      }
    }
  })

  it('respects per-node heights — taller nodes do not collide with neighbors', () => {
    // A wide range of heights — the v1 grid would have overlapped these.
    const nodes = [
      node('m.tall', 400),
      node('m.short', 80),
      node('m.medium', 200),
      node('m.alsoTall', 350),
      node('m.alsoShort', 90),
    ]
    const edges = [
      edge('m.tall', 'm.short'),
      edge('m.medium', 'm.short'),
      edge('m.alsoTall', 'm.medium'),
      edge('m.alsoShort', 'm.alsoTall'),
    ]
    const result = computeErdLayout(nodes, edges)

    const rects = nodes.map((n) => ({
      x: result[n.uid].x,
      y: result[n.uid].y,
      w: TABLE_W,
      h: n.height,
    }))
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        expect(overlaps(rects[i], rects[j])).toBe(false)
      }
    }
  })

  it('lays out disconnected nodes (orphan layer) without overlapping', () => {
    const nodes = [node('m.a'), node('m.b'), node('m.c')]
    const result = computeErdLayout(nodes, [])
    const rects = nodes.map((n) => ({
      x: result[n.uid].x,
      y: result[n.uid].y,
      w: TABLE_W,
      h: n.height,
    }))
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        expect(overlaps(rects[i], rects[j])).toBe(false)
      }
    }
  })

  it('places child to the left of parent (LR rankdir, child→parent edges)', () => {
    // Convention: ERD edges point child → parent (FK → PK). With rankdir=LR,
    // children land in earlier ranks (lower x) than their parents.
    const result = computeErdLayout(
      [node('m.child'), node('m.parent')],
      [edge('m.child', 'm.parent')],
    )
    expect(result['m.child'].x).toBeLessThan(result['m.parent'].x)
  })

  it('drops self-loops without throwing', () => {
    const result = computeErdLayout(
      [node('m.self')],
      [edge('m.self', 'm.self')],
    )
    expect(result['m.self']).toBeDefined()
  })

  it('drops edges referencing missing uids', () => {
    const result = computeErdLayout(
      [node('m.a')],
      [edge('m.a', 'm.ghost'), edge('m.ghost', 'm.a')],
    )
    expect(result['m.a']).toBeDefined()
    expect(result['m.ghost']).toBeUndefined()
  })

  it('deduplicates parallel edges between the same pair', () => {
    // Two relationships between (a, b) shouldn't warp the layout vs one.
    const a = computeErdLayout(
      [node('m.a'), node('m.b')],
      [edge('m.a', 'm.b')],
    )
    const b = computeErdLayout(
      [node('m.a'), node('m.b')],
      [edge('m.a', 'm.b'), edge('m.a', 'm.b'), edge('m.a', 'm.b')],
    )
    expect(a).toEqual(b)
  })

  it('is deterministic — same input yields identical output across calls', () => {
    const nodes = [node('m.x'), node('m.y'), node('m.z'), node('m.w')]
    const edges = [edge('m.x', 'm.y'), edge('m.z', 'm.w'), edge('m.y', 'm.w')]
    const a = computeErdLayout(nodes, edges)
    const b = computeErdLayout(nodes, edges)
    expect(a).toEqual(b)
  })

  it('does not mutate input arrays', () => {
    const nodes = [node('m.b'), node('m.a')]
    const edges = [edge('m.a', 'm.b')]
    const nodesBefore = nodes.map((n) => ({ ...n }))
    const edgesBefore = edges.map((e) => ({ ...e }))
    computeErdLayout(nodes, edges)
    expect(nodes).toEqual(nodesBefore)
    expect(edges).toEqual(edgesBefore)
  })
})

describe('computeErdLayout star ordering (#153)', () => {
  /** Dimension uids sorted top-to-bottom by their laid-out y. */
  const verticalOrder = (
    result: Record<string, { x: number; y: number }>,
    uids: readonly string[],
  ) => uids.slice().sort((a, b) => result[a].y - result[b].y)

  const dims = ['m.dim_a', 'm.dim_b', 'm.dim_c', 'm.dim_d', 'm.dim_e']
  const starNodes = [node('m.fact', 300), ...dims.map((d) => node(d, 100))]

  it('stacks dimension tables in the order of the fact table FK columns', () => {
    // Relationships arrive in an order unrelated to the fact table's columns.
    const fkColumn: Record<string, number> = {
      'm.dim_c': 0,
      'm.dim_a': 1,
      'm.dim_e': 2,
      'm.dim_b': 3,
      'm.dim_d': 4,
    }
    const edges = ['m.dim_d', 'm.dim_a', 'm.dim_b', 'm.dim_e', 'm.dim_c'].map(
      (to) => ({ from: 'm.fact', to, fromColumnIndex: fkColumn[to] }),
    )
    const result = computeErdLayout(starNodes, edges)
    expect(verticalOrder(result, dims)).toEqual([
      'm.dim_c',
      'm.dim_a',
      'm.dim_e',
      'm.dim_b',
      'm.dim_d',
    ])
    for (const d of dims) {
      expect(result['m.fact'].x).toBeLessThan(result[d].x)
    }
  })

  it('is unchanged from the plain layout when no edge carries a column index', () => {
    const edges = [
      edge('m.orders', 'm.customers'),
      edge('m.items', 'm.orders'),
      edge('m.items', 'm.products'),
    ]
    const nodes = [
      node('m.orders'),
      node('m.customers'),
      node('m.items'),
      node('m.products'),
    ]
    const withUndefined = edges.map((e) => ({ ...e, fromColumnIndex: undefined }))
    expect(computeErdLayout(nodes, withUndefined)).toEqual(
      computeErdLayout(nodes, edges),
    )
  })

  it('keeps edges without a column index after indexed ones, in input order', () => {
    const edges = [
      { from: 'm.fact', to: 'm.dim_a' },
      { from: 'm.fact', to: 'm.dim_b', fromColumnIndex: 1 },
      { from: 'm.fact', to: 'm.dim_c' },
      { from: 'm.fact', to: 'm.dim_d', fromColumnIndex: 0 },
    ]
    const nodes = starNodes.filter((n) => n.uid !== 'm.dim_e')
    const result = computeErdLayout(nodes, edges)
    expect(
      verticalOrder(result, ['m.dim_a', 'm.dim_b', 'm.dim_c', 'm.dim_d']),
    ).toEqual(['m.dim_d', 'm.dim_b', 'm.dim_a', 'm.dim_c'])
  })

  it('does not reorder edges across different source nodes', () => {
    // Index values only matter between edges that share a `from` node, so a
    // lone edge with a huge index must not move relative to other groups.
    const nodes = [node('m.a'), node('m.b'), node('m.c'), node('m.d')]
    const plain = [edge('m.a', 'm.b'), edge('m.c', 'm.d')]
    const indexed = [
      { ...edge('m.a', 'm.b'), fromColumnIndex: 99 },
      { ...edge('m.c', 'm.d'), fromColumnIndex: 0 },
    ]
    expect(computeErdLayout(nodes, indexed)).toEqual(
      computeErdLayout(nodes, plain),
    )
  })

  it('is deterministic and non-overlapping for an indexed star', () => {
    const edges = dims.map((to, i) => ({
      from: 'm.fact',
      to,
      fromColumnIndex: dims.length - i,
    }))
    const a = computeErdLayout(starNodes, edges)
    expect(computeErdLayout(starNodes, edges)).toEqual(a)
    const rects = starNodes.map((n) => ({
      x: a[n.uid].x,
      y: a[n.uid].y,
      w: TABLE_W,
      h: n.height,
    }))
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        expect(overlaps(rects[i], rects[j])).toBe(false)
      }
    }
  })
})
