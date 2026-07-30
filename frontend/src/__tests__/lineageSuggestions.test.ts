import { describe, it, expect } from 'vitest'
import { computeSuggestions } from '../utils/lineageSuggestions'
import type { LineageEdge, LineageNode } from '../types'

function node(id: string, resource_type: LineageNode['resource_type'] = 'model'): LineageNode {
  return {
    id,
    name: id,
    resource_type,
    materialization: 'table',
    schema: 'public',
    test_status: 'none',
    has_description: false,
    folder: 'models',
    tags: [],
  } as LineageNode
}

const NODES = [node('src', 'source'), node('a'), node('b'), node('c')]
const EDGES: LineageEdge[] = [
  { source: 'src', target: 'a' },
  { source: 'a', target: 'b' },
  { source: 'a', target: 'c' },
]

describe('computeSuggestions', () => {
  it('ranks models by total connections', () => {
    expect(computeSuggestions(NODES, EDGES).map(s => s.node.id)).toEqual(['a', 'b', 'c'])
  })

  it('counts upstream and downstream separately', () => {
    const a = computeSuggestions(NODES, EDGES).find(s => s.node.id === 'a')!
    expect(a.upstreamCount).toBe(1)
    expect(a.downstreamCount).toBe(2)
    expect(a.totalConnections).toBe(3)
  })

  it('excludes non-model nodes', () => {
    expect(computeSuggestions(NODES, EDGES).some(s => s.node.id === 'src')).toBe(false)
  })

  it('breaks ties by name so the order is stable', () => {
    const nodes = [node('zeta'), node('alpha')]
    expect(computeSuggestions(nodes, []).map(s => s.node.id)).toEqual(['alpha', 'zeta'])
  })

  it('honours the limit', () => {
    expect(computeSuggestions(NODES, EDGES, 2)).toHaveLength(2)
  })

  it('handles a project with no edges', () => {
    expect(computeSuggestions([node('a')], [])).toEqual([
      { node: node('a'), upstreamCount: 0, downstreamCount: 0, totalConnections: 0 },
    ])
  })
})
