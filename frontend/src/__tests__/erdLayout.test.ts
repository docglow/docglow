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

/**
 * Star schema from issue #153: one fact table with FK columns to five
 * dimension tables. Relationships arrive in a scrambled order (the order
 * that produced crossing lines in the issue's "current" screenshot).
 */
const FACT = 'm.fact_webshop_sales'
const FACT_COLUMNS = [
  'sales_id',
  'platform',
  'shop',
  'staat_code',
  'amount',
  're_gu_datum',
  'artikel_id',
]
/** Dimension uids in the order their FK columns appear on the fact. */
const DIMS_IN_FK_ORDER = [
  'm.dim_platform_group',
  'm.dim_shop_group',
  'm.dim_staat',
  'm.kalender',
  'm.dim_artikel',
]
const STAR_EDGES = [
  { from: FACT, to: 'm.dim_artikel', fromColumn: 'artikel_id' },
  { from: FACT, to: 'm.dim_platform_group', fromColumn: 'platform' },
  { from: FACT, to: 'm.kalender', fromColumn: 're_gu_datum' },
  { from: FACT, to: 'm.dim_shop_group', fromColumn: 'shop' },
  { from: FACT, to: 'm.dim_staat', fromColumn: 'staat_code' },
]
const STAR_NODES = [
  { uid: FACT, height: 250, columns: FACT_COLUMNS },
  { uid: 'm.dim_artikel', height: 114, columns: ['artikel_id'] },
  { uid: 'm.dim_platform_group', height: 114, columns: ['platform'] },
  { uid: 'm.kalender', height: 140, columns: ['kj_datum_nr'] },
  { uid: 'm.dim_shop_group', height: 88, columns: ['shop'] },
  { uid: 'm.dim_staat', height: 114, columns: ['staat_code'] },
]

function topToBottom(
  result: Record<string, { x: number; y: number }>,
  uids: readonly string[],
): string[] {
  return [...uids].sort((a, b) => result[a].y - result[b].y)
}

function withoutColumnInfo(
  nodes: readonly { uid: string; height: number }[],
  edges: readonly { from: string; to: string }[],
) {
  return {
    nodes: nodes.map(({ uid, height }) => ({ uid, height })),
    edges: edges.map(({ from, to }) => ({ from, to })),
  }
}

describe('computeErdLayout — star ordering (#153)', () => {
  it('stacks dimensions top-to-bottom in FK column order', () => {
    const result = computeErdLayout(STAR_NODES, STAR_EDGES)
    expect(topToBottom(result, DIMS_IN_FK_ORDER)).toEqual(DIMS_IN_FK_ORDER)
  })

  it('keeps dimensions in one column to the right of the fact table', () => {
    const result = computeErdLayout(STAR_NODES, STAR_EDGES)
    const dimXs = new Set(DIMS_IN_FK_ORDER.map((uid) => result[uid].x))
    expect(dimXs.size).toBe(1)
    expect(result[FACT].x).toBeLessThan(result[DIMS_IN_FK_ORDER[0]].x)
  })

  it('does not depend on the order relationships or nodes arrive in', () => {
    const reference = computeErdLayout(STAR_NODES, STAR_EDGES)
    const reversed = computeErdLayout(
      [...STAR_NODES].reverse(),
      [...STAR_EDGES].reverse(),
    )
    expect(topToBottom(reversed, DIMS_IN_FK_ORDER)).toEqual(DIMS_IN_FK_ORDER)
    expect(topToBottom(reference, DIMS_IN_FK_ORDER)).toEqual(
      topToBottom(reversed, DIMS_IN_FK_ORDER),
    )
  })

  it('is deterministic across runs', () => {
    const first = computeErdLayout(STAR_NODES, STAR_EDGES)
    for (let i = 0; i < 5; i++) {
      expect(computeErdLayout(STAR_NODES, STAR_EDGES)).toEqual(first)
    }
  })

  it('orders a dimension reached by several FK columns by its first one', () => {
    // A second FK to dim_artikel near the top of the fact pulls it up.
    const columns = ['sales_id', 'old_artikel_id', ...FACT_COLUMNS.slice(1)]
    const result = computeErdLayout(
      STAR_NODES.map((n) => (n.uid === FACT ? { ...n, columns } : n)),
      [...STAR_EDGES, { from: FACT, to: 'm.dim_artikel', fromColumn: 'old_artikel_id' }],
    )
    expect(topToBottom(result, DIMS_IN_FK_ORDER)).toEqual([
      'm.dim_artikel',
      'm.dim_platform_group',
      'm.dim_shop_group',
      'm.dim_staat',
      'm.kalender',
    ])
  })

  it('still orders the star when isolated tables are shown alongside it', () => {
    const result = computeErdLayout(
      [...STAR_NODES, node('m.isolated_a'), node('m.isolated_b')],
      STAR_EDGES,
    )
    expect(topToBottom(result, DIMS_IN_FK_ORDER)).toEqual(DIMS_IN_FK_ORDER)
  })

  describe('non-star graphs lay out exactly as before', () => {
    const cols = (uid: string, ...columns: string[]) => ({ uid, height: H, columns })
    const cases = {
      // dim_staat also has its own FK, so the fact is not the only source.
      snowflake: {
        nodes: [
          ...STAR_NODES,
          cols('m.dim_region', 'region_id'),
        ],
        edges: [
          ...STAR_EDGES,
          { from: 'm.dim_staat', to: 'm.dim_region', fromColumn: 'region_id' },
        ],
      },
      // Two fact tables sharing a dimension.
      twoFacts: {
        nodes: [
          cols('m.orders', 'order_id', 'customer_id', 'product_id'),
          cols('m.returns', 'return_id', 'product_id', 'customer_id'),
          cols('m.customers', 'customer_id'),
          cols('m.products', 'product_id'),
        ],
        edges: [
          { from: 'm.orders', to: 'm.products', fromColumn: 'product_id' },
          { from: 'm.orders', to: 'm.customers', fromColumn: 'customer_id' },
          { from: 'm.returns', to: 'm.customers', fromColumn: 'customer_id' },
          { from: 'm.returns', to: 'm.products', fromColumn: 'product_id' },
        ],
      },
      chain: {
        nodes: [
          cols('m.items', 'item_id', 'order_id'),
          cols('m.orders', 'order_id', 'customer_id'),
          cols('m.customers', 'customer_id'),
        ],
        edges: [
          { from: 'm.items', to: 'm.orders', fromColumn: 'order_id' },
          { from: 'm.orders', to: 'm.customers', fromColumn: 'customer_id' },
        ],
      },
    }

    for (const [name, { nodes, edges }] of Object.entries(cases)) {
      it(name, () => {
        const legacy = withoutColumnInfo(nodes, edges)
        expect(computeErdLayout(nodes, edges)).toEqual(
          computeErdLayout(legacy.nodes, legacy.edges),
        )
      })
    }
  })
})
