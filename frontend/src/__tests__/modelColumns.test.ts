import { describe, it, expect } from 'vitest'
import { buildModelColumnsMap } from '../utils/modelColumns'
import type { DocglowData } from '../types'

function makeData(withColumnLineage: boolean): DocglowData {
  return {
    models: { 'model.p.orders': { columns: [{ name: 'amount' }] } },
    sources: {},
    metrics: {
      'metric.p.revenue': { unique_id: 'metric.p.revenue', name: 'revenue' },
      'metric.p.row_count': { unique_id: 'metric.p.row_count', name: 'row_count' },
    },
    column_lineage: withColumnLineage
      ? {
          'metric.p.revenue': {
            revenue: [{ source_model: 'model.p.orders', source_column: 'amount', transformation: 'aggregated' }],
          },
        }
      : undefined,
  } as unknown as DocglowData
}

describe('buildModelColumnsMap', () => {
  it('gives a metric in column lineage one column, named after itself', () => {
    const map = buildModelColumnsMap(makeData(true))
    expect(map['model.p.orders']).toEqual(['amount'])
    expect(map['metric.p.revenue']).toEqual(['revenue'])
    // No column lineage entry (a row count reads no column): nothing to expand.
    expect(map['metric.p.row_count']).toBeUndefined()
  })

  it('adds no metrics when column lineage is off', () => {
    expect(buildModelColumnsMap(makeData(false))['metric.p.revenue']).toBeUndefined()
  })
})
