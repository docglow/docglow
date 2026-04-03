import { describe, it, expect } from 'vitest'
import type { ColumnLineageData, ColumnEdge } from '../types'
import { getColumnTraceResult, buildReverseIndex } from '../utils/columnLineageGraph'

/**
 * These tests verify the data computation logic that powers the ColumnTraceDrawer:
 * trace result generation, upstream/downstream counting, and edge cases.
 */

function makeLineageData(entries: {
  targetModel: string
  targetColumn: string
  sourceModel: string
  sourceColumn: string
  transformation: ColumnEdge['transformation']
}[]): ColumnLineageData {
  const data: Record<string, Record<string, { source_model: string; source_column: string; transformation: string }[]>> = {}
  for (const e of entries) {
    if (!data[e.targetModel]) data[e.targetModel] = {}
    if (!data[e.targetModel][e.targetColumn]) data[e.targetModel][e.targetColumn] = []
    data[e.targetModel][e.targetColumn].push({
      source_model: e.sourceModel,
      source_column: e.sourceColumn,
      transformation: e.transformation,
    })
  }
  return data as ColumnLineageData
}

describe('ColumnTraceDrawer data logic', () => {
  describe('trace result for drawer display', () => {
    it('returns empty edges when column has no lineage', () => {
      const lineageData: ColumnLineageData = {}
      const reverseIndex = buildReverseIndex(lineageData)
      const result = getColumnTraceResult('model.orders', 'status', lineageData, reverseIndex)

      expect(result.edges).toHaveLength(0)
      expect(result.highlightedColumns.size).toBe(1) // just the selected column itself
      expect(result.highlightedColumns.get('model.orders')?.has('status')).toBe(true)
    })

    it('traces upstream-only column', () => {
      const lineageData = makeLineageData([
        {
          targetModel: 'model.orders',
          targetColumn: 'order_id',
          sourceModel: 'source.raw_orders',
          sourceColumn: 'id',
          transformation: 'passthrough',
        },
      ])
      const reverseIndex = buildReverseIndex(lineageData)
      const result = getColumnTraceResult('model.orders', 'order_id', lineageData, reverseIndex)

      expect(result.edges).toHaveLength(1)
      expect(result.edges[0].sourceModel).toBe('source.raw_orders')
      expect(result.edges[0].targetModel).toBe('model.orders')
      expect(result.highlightedColumns.size).toBe(2)
    })

    it('traces downstream-only column', () => {
      const lineageData = makeLineageData([
        {
          targetModel: 'model.downstream',
          targetColumn: 'user_id',
          sourceModel: 'model.users',
          sourceColumn: 'user_id',
          transformation: 'passthrough',
        },
      ])
      const reverseIndex = buildReverseIndex(lineageData)
      const result = getColumnTraceResult('model.users', 'user_id', lineageData, reverseIndex)

      expect(result.edges).toHaveLength(1)
      expect(result.edges[0].sourceModel).toBe('model.users')
      expect(result.edges[0].targetModel).toBe('model.downstream')
    })

    it('traces full chain: upstream + downstream', () => {
      const lineageData = makeLineageData([
        {
          targetModel: 'model.stg_orders',
          targetColumn: 'order_id',
          sourceModel: 'source.raw_orders',
          sourceColumn: 'id',
          transformation: 'passthrough',
        },
        {
          targetModel: 'model.orders',
          targetColumn: 'order_id',
          sourceModel: 'model.stg_orders',
          sourceColumn: 'order_id',
          transformation: 'passthrough',
        },
      ])
      const reverseIndex = buildReverseIndex(lineageData)
      const result = getColumnTraceResult('model.stg_orders', 'order_id', lineageData, reverseIndex)

      // Should have upstream edge (raw → stg) and downstream edge (stg → orders)
      expect(result.edges).toHaveLength(2)

      const sourceModels = result.edges.map((e) => e.sourceModel)
      expect(sourceModels).toContain('source.raw_orders')
      expect(sourceModels).toContain('model.stg_orders')

      // All three models should be highlighted
      expect(result.highlightedColumns.size).toBe(3)
    })

    it('handles fan-in: multiple sources feeding one column', () => {
      const lineageData = makeLineageData([
        {
          targetModel: 'model.orders',
          targetColumn: 'total',
          sourceModel: 'source.raw_orders',
          sourceColumn: 'subtotal',
          transformation: 'derived',
        },
        {
          targetModel: 'model.orders',
          targetColumn: 'total',
          sourceModel: 'source.raw_tax',
          sourceColumn: 'tax_amount',
          transformation: 'aggregated',
        },
      ])
      const reverseIndex = buildReverseIndex(lineageData)
      const result = getColumnTraceResult('model.orders', 'total', lineageData, reverseIndex)

      expect(result.edges).toHaveLength(2)
      expect(result.highlightedColumns.size).toBe(3)
    })

    it('handles fan-out: one column consumed by multiple downstream', () => {
      const lineageData = makeLineageData([
        {
          targetModel: 'model.report_a',
          targetColumn: 'user_id',
          sourceModel: 'model.users',
          sourceColumn: 'user_id',
          transformation: 'passthrough',
        },
        {
          targetModel: 'model.report_b',
          targetColumn: 'actor_id',
          sourceModel: 'model.users',
          sourceColumn: 'user_id',
          transformation: 'derived',
        },
      ])
      const reverseIndex = buildReverseIndex(lineageData)
      const result = getColumnTraceResult('model.users', 'user_id', lineageData, reverseIndex)

      expect(result.edges).toHaveLength(2)
      expect(result.highlightedColumns.size).toBe(3)
    })

    it('respects max depth and does not trace infinitely', () => {
      // Build a long chain of 15 models (m0 → m1 → ... → m14)
      const entries = []
      for (let i = 0; i < 14; i++) {
        entries.push({
          targetModel: `model.m${i + 1}`,
          targetColumn: 'col',
          sourceModel: `model.m${i}`,
          sourceColumn: 'col',
          transformation: 'passthrough' as const,
        })
      }
      const lineageData = makeLineageData(entries)
      const reverseIndex = buildReverseIndex(lineageData)

      // Trace from start (m0), default depth = 6
      // Upstream: 0 edges (m0 is the root)
      // Downstream: limited to 6 hops, so m0→m1→...→m6 = 6 edges
      const result = getColumnTraceResult('model.m0', 'col', lineageData, reverseIndex)

      // Should not trace all 14 edges — limited by depth 6
      expect(result.edges.length).toBeLessThan(14)
      expect(result.edges.length).toBeGreaterThan(0)
      // Exactly 6 downstream edges
      expect(result.edges.length).toBe(6)
    })
  })

  describe('buildReverseIndex', () => {
    it('builds correct reverse mappings', () => {
      const lineageData = makeLineageData([
        {
          targetModel: 'model.orders',
          targetColumn: 'user_id',
          sourceModel: 'model.users',
          sourceColumn: 'user_id',
          transformation: 'passthrough',
        },
      ])
      const index = buildReverseIndex(lineageData)

      const consumers = index.get('model.users::user_id')
      expect(consumers).toHaveLength(1)
      expect(consumers![0].modelId).toBe('model.orders')
      expect(consumers![0].columnName).toBe('user_id')
    })

    it('returns empty map for empty lineage data', () => {
      const index = buildReverseIndex({})
      expect(index.size).toBe(0)
    })
  })
})
