import { describe, it, expect } from 'vitest'
import { buildTraceLayout } from '../utils/columnTraceLayout'
import type { ColumnEdge } from '../types'

function makeEdge(
  sourceModel: string,
  sourceColumn: string,
  targetModel: string,
  targetColumn: string,
  transformation: ColumnEdge['transformation'] = 'passthrough',
): ColumnEdge {
  return { sourceModel, sourceColumn, targetModel, targetColumn, transformation }
}

describe('buildTraceLayout', () => {
  it('returns empty result for empty edges', () => {
    const result = buildTraceLayout([], 'model.orders', 'id')
    expect(result.nodes).toHaveLength(0)
    expect(result.edges).toHaveLength(0)
  })

  it('handles a linear chain (A → B → C)', () => {
    const edges: ColumnEdge[] = [
      makeEdge('source.raw_orders', 'order_id', 'model.stg_orders', 'order_id'),
      makeEdge('model.stg_orders', 'order_id', 'model.orders', 'order_id'),
    ]

    const result = buildTraceLayout(edges, 'model.stg_orders', 'order_id')

    expect(result.nodes).toHaveLength(3)
    expect(result.edges).toHaveLength(2)

    // All three models should be present
    const nodeIds = result.nodes.map((n) => n.id).sort()
    expect(nodeIds).toEqual([
      'model.orders',
      'model.stg_orders',
      'source.raw_orders',
    ])

    // Current model should be marked
    const currentNode = result.nodes.find((n) => n.id === 'model.stg_orders')
    expect(currentNode?.data.isCurrent).toBe(true)
    expect(currentNode?.data.currentColumn).toBe('order_id')

    // Other nodes should not be current
    const otherNode = result.nodes.find((n) => n.id === 'source.raw_orders')
    expect(otherNode?.data.isCurrent).toBe(false)
    expect(otherNode?.data.currentColumn).toBeNull()
  })

  it('handles fan-out (one source → multiple targets)', () => {
    const edges: ColumnEdge[] = [
      makeEdge('model.users', 'user_id', 'model.orders', 'user_id', 'passthrough'),
      makeEdge('model.users', 'user_id', 'model.sessions', 'user_id', 'passthrough'),
      makeEdge('model.users', 'user_id', 'model.events', 'actor_id', 'derived'),
    ]

    const result = buildTraceLayout(edges, 'model.users', 'user_id')

    expect(result.nodes).toHaveLength(4)
    expect(result.edges).toHaveLength(3)

    // Each edge should have the correct transformation color
    const derivedEdge = result.edges.find(
      (e) => e.target === 'model.events',
    )
    expect(derivedEdge?.style?.stroke).toBe('#d97706') // derived = amber
  })

  it('handles fan-in (multiple sources → one target)', () => {
    const edges: ColumnEdge[] = [
      makeEdge('source.raw_orders', 'total', 'model.orders', 'total_amount', 'passthrough'),
      makeEdge('source.raw_tax', 'tax_rate', 'model.orders', 'total_amount', 'aggregated'),
    ]

    const result = buildTraceLayout(edges, 'model.orders', 'total_amount')

    expect(result.nodes).toHaveLength(3)
    expect(result.edges).toHaveLength(2)

    // Model.orders should have one column: total_amount
    const ordersNode = result.nodes.find((n) => n.id === 'model.orders')
    expect(ordersNode?.data.columns).toContain('total_amount')
  })

  it('deduplicates models but keeps separate column entries', () => {
    const edges: ColumnEdge[] = [
      makeEdge('model.stg_orders', 'order_id', 'model.orders', 'order_id'),
      makeEdge('model.stg_orders', 'amount', 'model.orders', 'amount'),
    ]

    const result = buildTraceLayout(edges, 'model.orders', 'order_id')

    // Should only have 2 model nodes, not 4
    expect(result.nodes).toHaveLength(2)
    // But 2 edges (one per column pair)
    expect(result.edges).toHaveLength(2)

    // Each model should have both columns
    const stgNode = result.nodes.find((n) => n.id === 'model.stg_orders')
    expect(stgNode?.data.columns).toContain('order_id')
    expect(stgNode?.data.columns).toContain('amount')
  })

  it('sets correct node type for all nodes', () => {
    const edges: ColumnEdge[] = [
      makeEdge('source.raw', 'col', 'model.stg', 'col'),
    ]

    const result = buildTraceLayout(edges, 'model.stg', 'col')

    for (const node of result.nodes) {
      expect(node.type).toBe('columnTrace')
    }
  })

  it('extracts resource type and model name from model ID', () => {
    const edges: ColumnEdge[] = [
      makeEdge('source.my_db.raw_orders', 'id', 'model.stg_orders', 'id'),
    ]

    const result = buildTraceLayout(edges, 'model.stg_orders', 'id')

    const sourceNode = result.nodes.find((n) => n.id === 'source.my_db.raw_orders')
    expect(sourceNode?.data.resourceType).toBe('source')
    expect(sourceNode?.data.modelName).toBe('raw_orders')

    const modelNode = result.nodes.find((n) => n.id === 'model.stg_orders')
    expect(modelNode?.data.resourceType).toBe('model')
    expect(modelNode?.data.modelName).toBe('stg_orders')
  })

  it('positions nodes left-to-right (upstream x < downstream x)', () => {
    const edges: ColumnEdge[] = [
      makeEdge('source.raw', 'id', 'model.stg', 'id'),
      makeEdge('model.stg', 'id', 'model.final', 'id'),
    ]

    const result = buildTraceLayout(edges, 'model.stg', 'id')

    const rawX = result.nodes.find((n) => n.id === 'source.raw')!.position.x
    const stgX = result.nodes.find((n) => n.id === 'model.stg')!.position.x
    const finalX = result.nodes.find((n) => n.id === 'model.final')!.position.x

    expect(rawX).toBeLessThan(stgX)
    expect(stgX).toBeLessThan(finalX)
  })

  it('animates passthrough/direct edges but not others', () => {
    const edges: ColumnEdge[] = [
      makeEdge('model.a', 'col', 'model.b', 'col', 'passthrough'),
      makeEdge('model.b', 'col', 'model.c', 'col', 'derived'),
      makeEdge('model.c', 'col', 'model.d', 'col', 'direct'),
    ]

    const result = buildTraceLayout(edges, 'model.b', 'col')

    const passthroughEdge = result.edges.find((e) => e.source === 'model.a')
    expect(passthroughEdge?.animated).toBe(true)

    const derivedEdge = result.edges.find((e) => e.source === 'model.b')
    expect(derivedEdge?.animated).toBe(false)

    const directEdge = result.edges.find((e) => e.source === 'model.c')
    expect(directEdge?.animated).toBe(true)
  })
})
