import { describe, it, expect } from 'vitest'
import { buildProjectMap, nodesInLayer } from '../utils/projectMap'
import type { DocglowData, LayerDefinition, LineageNode } from '../types'

function node(id: string, layer: number | undefined, name = id): LineageNode {
  return {
    id,
    name,
    resource_type: 'model',
    materialization: 'table',
    schema: 'public',
    test_status: 'none',
    has_description: false,
    folder: 'models',
    tags: [],
    ...(layer === undefined ? {} : { layer }),
  } as LineageNode
}

const LAYERS: LayerDefinition[] = [
  { name: 'source', rank: 0, color: '#dcfce7' },
  { name: 'staging', rank: 1, color: '#dbeafe' },
  { name: 'mart', rank: 3, color: '#fce7f3' },
  { name: 'exposure', rank: 4, color: '#f3e8ff' },
]

function makeData(nodes: LineageNode[], layer_config?: LayerDefinition[]): DocglowData {
  return { lineage: { nodes, edges: [], layer_config } } as unknown as DocglowData
}

describe('buildProjectMap', () => {
  it('orders populated layers by rank with their counts', () => {
    const data = makeData(
      [node('a', 0), node('b', 1), node('c', 1), node('d', 3)],
      LAYERS,
    )
    expect(buildProjectMap(data)).toEqual([
      { rank: 0, name: 'source', label: 'Source', color: '#dcfce7', count: 1 },
      { rank: 1, name: 'staging', label: 'Staging', color: '#dbeafe', count: 2 },
      { rank: 3, name: 'mart', label: 'Mart', color: '#fce7f3', count: 1 },
    ])
  })

  it('drops empty layers rather than rendering them as zero', () => {
    // A project with no exposures has not failed to fill one in.
    const data = makeData([node('a', 0), node('b', 1)], LAYERS)
    expect(buildProjectMap(data).map(s => s.name)).toEqual(['source', 'staging'])
  })

  it('returns nothing when only one layer is populated', () => {
    const data = makeData([node('a', 1), node('b', 1)], LAYERS)
    expect(buildProjectMap(data)).toEqual([])
  })

  it('returns nothing when no node carries a layer', () => {
    const data = makeData([node('a', undefined), node('b', undefined)], LAYERS)
    expect(buildProjectMap(data)).toEqual([])
  })

  it('synthesises layers when the payload has no layer_config', () => {
    const data = makeData([node('a', 0), node('b', 2)])
    expect(buildProjectMap(data)).toEqual([
      { rank: 0, name: 'Layer 0', label: 'Layer 0', color: '#e2e8f0', count: 1 },
      { rank: 2, name: 'Layer 2', label: 'Layer 2', color: '#e2e8f0', count: 1 },
    ])
  })

  it('ignores configured layers that the project does not use', () => {
    const data = makeData([node('a', 0), node('b', 1)], [
      ...LAYERS,
      { name: 'unused', rank: 9, color: '#000' },
    ])
    expect(buildProjectMap(data).some(s => s.name === 'unused')).toBe(false)
  })
})

describe('nodesInLayer', () => {
  it('returns only that layer, name-sorted', () => {
    const data = makeData([
      node('m3', 1, 'zeta'),
      node('m1', 1, 'alpha'),
      node('m2', 3, 'beta'),
    ], LAYERS)
    expect(nodesInLayer(data, 1).map(n => n.name)).toEqual(['alpha', 'zeta'])
  })

  it('returns an empty list for an unpopulated rank', () => {
    expect(nodesInLayer(makeData([node('a', 1)], LAYERS), 4)).toEqual([])
  })
})
