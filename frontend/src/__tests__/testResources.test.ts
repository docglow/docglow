import { describe, it, expect } from 'vitest'
import {
  resolveResource,
  resourceCell,
  testResourceIds,
  type ResourceMaps,
} from '../utils/testResources'
import type { DocglowModel, DocglowSource, ProjectTest } from '../types'

// Only the fields the resolver reads; cast keeps the fixture readable.
const model = (name: string) => ({ name }) as unknown as DocglowModel
const source = (source_name: string, name: string) =>
  ({ source_name, name }) as unknown as DocglowSource

const data: ResourceMaps = {
  models: {
    'model.jaffle_shop.orders': model('orders'),
    'model.jaffle_shop.stg_customers': model('stg_customers'),
  },
  seeds: { 'seed.jaffle_shop.raw_items': model('raw_items') },
  snapshots: { 'snapshot.jaffle_shop.orders_snap': model('orders_snap') },
  sources: { 'source.jaffle_shop.ecom.raw_orders': source('ecom', 'raw_orders') },
}

function makeTest(overrides: Partial<ProjectTest> = {}): ProjectTest {
  return {
    unique_id: 'test.jaffle_shop.t',
    name: 't',
    test_type: 'not_null',
    is_generic: true,
    column_name: 'id',
    severity: 'error',
    status: 'pass',
    failures: 0,
    execution_time: 0.01,
    package_name: 'jaffle_shop',
    original_file_path: 'models/x.yml',
    attached_node: 'model.jaffle_shop.orders',
    references: [],
    ...overrides,
  }
}

describe('resolveResource', () => {
  it('resolves models, seeds, and snapshots to /model routes', () => {
    expect(resolveResource('model.jaffle_shop.orders', data)).toEqual({
      uid: 'model.jaffle_shop.orders',
      name: 'orders',
      path: '/model/model.jaffle_shop.orders',
    })
    expect(resolveResource('seed.jaffle_shop.raw_items', data).path).toBe(
      '/model/seed.jaffle_shop.raw_items',
    )
    expect(resolveResource('snapshot.jaffle_shop.orders_snap', data).name).toBe('orders_snap')
  })

  it('shows sources as source_name.name on a /source route', () => {
    expect(resolveResource('source.jaffle_shop.ecom.raw_orders', data)).toEqual({
      uid: 'source.jaffle_shop.ecom.raw_orders',
      name: 'ecom.raw_orders',
      path: '/source/source.jaffle_shop.ecom.raw_orders',
    })
  })

  it('never links to a resource missing from the payload (e.g. filtered by --select)', () => {
    expect(resolveResource('model.jaffle_shop.not_generated', data)).toEqual({
      uid: 'model.jaffle_shop.not_generated',
      name: 'not_generated',
      path: null,
    })
  })
})

describe('resourceCell', () => {
  it('uses attached_node for a relationships test, not the referenced model', () => {
    // dbt: depends_on.nodes = [stg_customers, orders]; attached_node = orders.
    const test = makeTest({
      test_type: 'relationships',
      attached_node: 'model.jaffle_shop.orders',
      references: ['model.jaffle_shop.stg_customers'],
    })
    expect(resourceCell(test)).toEqual({ kind: 'single', uid: 'model.jaffle_shop.orders' })
    expect(testResourceIds(test)).toEqual([
      'model.jaffle_shop.orders',
      'model.jaffle_shop.stg_customers',
    ])
  })

  it('shows the only resource of a single-resource singular test', () => {
    const test = makeTest({
      test_type: 'singular',
      is_generic: false,
      attached_node: undefined,
      references: ['model.jaffle_shop.orders'],
    })
    expect(resourceCell(test)).toEqual({ kind: 'single', uid: 'model.jaffle_shop.orders' })
  })

  it('promotes no primary for a multi-resource singular test', () => {
    const uids = ['model.jaffle_shop.orders', 'source.jaffle_shop.ecom.raw_orders']
    const test = makeTest({
      test_type: 'singular',
      is_generic: false,
      attached_node: undefined,
      references: uids,
    })
    expect(resourceCell(test)).toEqual({ kind: 'many', uids })
  })

  it('handles the wire format, where empty optional keys are omitted', () => {
    // As emitted by the generator for a passing generic test with no extra refs.
    const fromPayload = JSON.parse(
      JSON.stringify({
        unique_id: 'test.jaffle_shop.unique_orders_order_id',
        name: 'unique_orders_order_id',
        test_type: 'unique',
        is_generic: true,
        column_name: 'order_id',
        severity: 'error',
        status: 'pass',
        failures: 0,
        execution_time: 0.01,
        package_name: 'jaffle_shop',
        original_file_path: 'models/orders.yml',
        attached_node: 'model.jaffle_shop.orders',
      }),
    ) as ProjectTest
    expect('references' in fromPayload).toBe(false)
    expect(resourceCell(fromPayload)).toEqual({ kind: 'single', uid: 'model.jaffle_shop.orders' })
    expect(testResourceIds(fromPayload)).toEqual(['model.jaffle_shop.orders'])
  })

  it('is empty when a test touches no resource', () => {
    expect(resourceCell(makeTest({ attached_node: undefined, references: [] }))).toEqual({
      kind: 'none',
    })
  })
})
