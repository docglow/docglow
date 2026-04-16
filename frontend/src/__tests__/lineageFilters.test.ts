import { describe, it, expect } from 'vitest'
import { applyFilters, computeSubgraphOptions, EMPTY_FILTER } from '../utils/lineageFilters'
import type { FilterState } from '../components/ui/FilterDropdown'
import type { LineageNode, LineageEdge } from '../types'

function makeNode(overrides: Partial<LineageNode> & { id: string }): LineageNode {
  return {
    name: overrides.id,
    resource_type: 'model',
    materialization: 'view',
    schema: 'public',
    test_status: 'none',
    has_description: false,
    folder: 'models/',
    tags: [],
    ...overrides,
  }
}

function makeEdge(source: string, target: string): LineageEdge {
  return { source, target }
}

describe('applyFilters — tag filtering', () => {
  const nodes: LineageNode[] = [
    makeNode({ id: 'a', tags: ['finance', 'daily'] }),
    makeNode({ id: 'b', tags: ['marketing'] }),
    makeNode({ id: 'c', tags: ['finance', 'marketing'] }),
    makeNode({ id: 'd', tags: [] }),
  ]
  const edges: LineageEdge[] = [
    makeEdge('a', 'b'),
    makeEdge('b', 'c'),
    makeEdge('c', 'd'),
    makeEdge('a', 'c'),
  ]

  it('returns all nodes when tag filter is empty', () => {
    const result = applyFilters(nodes, edges, EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER)
    expect(result.nodes).toHaveLength(4)
    expect(result.edges).toHaveLength(4)
  })

  it('includes only nodes matching selected tags in include mode', () => {
    const tagFilter: FilterState = { mode: 'include', selected: new Set(['finance']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, tagFilter, EMPTY_FILTER)

    const ids = result.nodes.map(n => n.id)
    expect(ids).toContain('a')
    expect(ids).toContain('c')
    expect(ids).not.toContain('b')
    expect(ids).not.toContain('d')
  })

  it('excludes nodes matching selected tags in exclude mode', () => {
    const tagFilter: FilterState = { mode: 'exclude', selected: new Set(['finance']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, tagFilter, EMPTY_FILTER)

    const ids = result.nodes.map(n => n.id)
    expect(ids).not.toContain('a')
    expect(ids).not.toContain('c')
    expect(ids).toContain('b')
    expect(ids).toContain('d')
  })

  it('include mode with multiple tags uses OR logic (any tag matches)', () => {
    const tagFilter: FilterState = { mode: 'include', selected: new Set(['finance', 'marketing']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, tagFilter, EMPTY_FILTER)

    const ids = result.nodes.map(n => n.id)
    expect(ids).toEqual(expect.arrayContaining(['a', 'b', 'c']))
    expect(ids).not.toContain('d')
  })

  it('exclude mode with multiple tags excludes nodes matching any tag', () => {
    const tagFilter: FilterState = { mode: 'exclude', selected: new Set(['finance', 'marketing']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, tagFilter, EMPTY_FILTER)

    const ids = result.nodes.map(n => n.id)
    // a has finance, b has marketing, c has both — all excluded
    expect(ids).toEqual(['d'])
  })

  it('filters edges to only connect surviving nodes', () => {
    const tagFilter: FilterState = { mode: 'include', selected: new Set(['finance']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, tagFilter, EMPTY_FILTER)

    // Only a and c survive, so only a->c edge survives
    expect(result.edges).toHaveLength(1)
    expect(result.edges[0]).toEqual({ source: 'a', target: 'c' })
  })

  it('combines tag filter with type filter', () => {
    const nodesWithTypes = [
      makeNode({ id: 'a', tags: ['finance'], resource_type: 'model' }),
      makeNode({ id: 'b', tags: ['finance'], resource_type: 'source' }),
    ]
    const typeFilter: FilterState = { mode: 'include', selected: new Set(['model']) }
    const tagFilter: FilterState = { mode: 'include', selected: new Set(['finance']) }
    const result = applyFilters(nodesWithTypes, [], typeFilter, tagFilter, EMPTY_FILTER)

    expect(result.nodes).toHaveLength(1)
    expect(result.nodes[0].id).toBe('a')
  })
})

describe('computeSubgraphOptions — tag collection', () => {
  it('collects and deduplicates tags from nodes', () => {
    const nodes: LineageNode[] = [
      makeNode({ id: 'a', tags: ['finance', 'daily'] }),
      makeNode({ id: 'b', tags: ['marketing', 'daily'] }),
      makeNode({ id: 'c', tags: [] }),
    ]

    const options = computeSubgraphOptions(nodes)
    expect(options.tags).toEqual(['daily', 'finance', 'marketing'])
  })

  it('returns empty tags when no nodes have tags', () => {
    const nodes: LineageNode[] = [
      makeNode({ id: 'a', tags: [] }),
      makeNode({ id: 'b', tags: [] }),
    ]

    const options = computeSubgraphOptions(nodes)
    expect(options.tags).toEqual([])
  })

  it('returns sorted tags', () => {
    const nodes: LineageNode[] = [
      makeNode({ id: 'a', tags: ['zebra', 'alpha', 'middle'] }),
    ]

    const options = computeSubgraphOptions(nodes)
    expect(options.tags).toEqual(['alpha', 'middle', 'zebra'])
  })
})

describe('applyFilters — layer filtering', () => {
  const nodes: LineageNode[] = [
    makeNode({ id: 'a', layer: 0 }),
    makeNode({ id: 'b', layer: 1 }),
    makeNode({ id: 'c', layer: 2 }),
    makeNode({ id: 'd', layer: 1 }),
  ]
  const edges: LineageEdge[] = [
    makeEdge('a', 'b'),
    makeEdge('b', 'c'),
    makeEdge('d', 'c'),
  ]

  it('returns all nodes when layer filter is empty', () => {
    const result = applyFilters(nodes, edges, EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER)
    expect(result.nodes).toHaveLength(4)
  })

  it('includes only nodes in selected layers (include mode)', () => {
    const layerFilter: FilterState = { mode: 'include', selected: new Set(['1']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER, layerFilter)
    const ids = result.nodes.map(n => n.id).sort()
    expect(ids).toEqual(['b', 'd'])
  })

  it('excludes nodes in selected layers (exclude mode)', () => {
    const layerFilter: FilterState = { mode: 'exclude', selected: new Set(['1']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER, layerFilter)
    const ids = result.nodes.map(n => n.id).sort()
    expect(ids).toEqual(['a', 'c'])
  })

  it('excludes nodes without a layer in include mode', () => {
    const nodesWithUnassigned = [...nodes, makeNode({ id: 'e' })]
    const layerFilter: FilterState = { mode: 'include', selected: new Set(['1']) }
    const result = applyFilters(nodesWithUnassigned, [], EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER, layerFilter)
    expect(result.nodes.map(n => n.id)).not.toContain('e')
  })

  it('keeps nodes without a layer in exclude mode', () => {
    const nodesWithUnassigned = [...nodes, makeNode({ id: 'e' })]
    const layerFilter: FilterState = { mode: 'exclude', selected: new Set(['1']) }
    const result = applyFilters(nodesWithUnassigned, [], EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER, layerFilter)
    expect(result.nodes.map(n => n.id)).toContain('e')
  })

  it('also filters edges when layer filter hides endpoints', () => {
    const layerFilter: FilterState = { mode: 'include', selected: new Set(['1']) }
    const result = applyFilters(nodes, edges, EMPTY_FILTER, EMPTY_FILTER, EMPTY_FILTER, layerFilter)
    // Only b and d survive; no edges connect both of them
    expect(result.edges).toHaveLength(0)
  })
})

describe('computeSubgraphOptions — layer collection', () => {
  it('collects unique layers from nodes', () => {
    const nodes: LineageNode[] = [
      makeNode({ id: 'a', layer: 0 }),
      makeNode({ id: 'b', layer: 1 }),
      makeNode({ id: 'c', layer: 1 }),
    ]
    const options = computeSubgraphOptions(nodes)
    expect(options.layers).toEqual(['0', '1'])
  })

  it('returns empty layers when no nodes are assigned', () => {
    const nodes: LineageNode[] = [makeNode({ id: 'a' }), makeNode({ id: 'b' })]
    const options = computeSubgraphOptions(nodes)
    expect(options.layers).toEqual([])
  })

  it('sorts layers numerically (not lexicographically)', () => {
    const nodes: LineageNode[] = [
      makeNode({ id: 'a', layer: 10 }),
      makeNode({ id: 'b', layer: 2 }),
      makeNode({ id: 'c', layer: 1 }),
    ]
    const options = computeSubgraphOptions(nodes)
    expect(options.layers).toEqual(['1', '2', '10'])
  })
})
