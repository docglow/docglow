import { describe, it, expect } from 'vitest'
import { buildTree, collectFolderPaths } from '../utils/sidebarTree'
import type { DocglowExposure, DocglowModel, DocglowSource } from '../types'

function makeNode(
  resourceType: string,
  name: string,
  path: string,
  tags: string[] = [],
): DocglowModel {
  return {
    unique_id: `${resourceType}.project.${name}`,
    name,
    description: '',
    path,
    schema: 'public',
    database: 'db',
    materialization: resourceType === 'model' ? 'view' : resourceType,
    columns: [],
    tags,
    test_results: [],
    depends_on: [],
    referenced_by: [],
    meta: {},
  } as unknown as DocglowModel
}

function makeModel(name: string, path = `models/${name}.sql`, tags: string[] = []): DocglowModel {
  return makeNode('model', name, path, tags)
}

function makeSnapshot(name: string, path = `snapshots/${name}.sql`, tags: string[] = []): DocglowModel {
  return makeNode('snapshot', name, path, tags)
}

function makeSeed(name: string, path = `seeds/${name}.csv`, tags: string[] = []): DocglowModel {
  return makeNode('seed', name, path, tags)
}

function makeSource(name: string, sourceName = 'raw'): DocglowSource {
  return {
    unique_id: `source.project.${sourceName}.${name}`,
    name,
    source_name: sourceName,
    description: '',
    schema: 'public',
    database: 'db',
    columns: [],
    tags: [],
    meta: {},
  } as unknown as DocglowSource
}

function makeExposure(name: string): DocglowExposure {
  return {
    unique_id: `exposure.project.${name}`,
    name,
    tags: [],
  } as unknown as DocglowExposure
}

describe('buildTree', () => {
  it('builds models under nested folders', () => {
    const tree = buildTree(
      {
        'model.project.stg_orders': makeModel('stg_orders', 'models/staging/stg_orders.sql'),
        'model.project.orders': makeModel('orders', 'models/marts/orders.sql'),
      },
      {},
      {},
    )
    const models = tree.children.get('models')!
    expect([...models.children.keys()].sort()).toEqual(['marts', 'staging'])
    const staging = models.children.get('staging')!
    expect(staging.children.get('stg_orders')!.resourceType).toBe('model')
  })

  it('renders a snapshots section with folder structure and snapshot leaves', () => {
    const tree = buildTree(
      {},
      {},
      {},
      {},
      {
        'snapshot.project.orders_snapshot': makeSnapshot('orders_snapshot'),
        'snapshot.project.legacy_snap': makeSnapshot('legacy_snap', 'snapshots/legacy/legacy_snap.sql'),
      },
    )
    const snapshots = tree.children.get('snapshots')!
    expect(snapshots).toBeDefined()
    const leaf = snapshots.children.get('orders_snapshot')!
    expect(leaf.uniqueId).toBe('snapshot.project.orders_snapshot')
    expect(leaf.resourceType).toBe('snapshot')
    const legacyFolder = snapshots.children.get('legacy')!
    expect(legacyFolder.children.get('legacy_snap')!.resourceType).toBe('snapshot')
  })

  it('renders a seeds section with seed leaves', () => {
    const tree = buildTree(
      {},
      {},
      {},
      { 'seed.project.raw_customers': makeSeed('raw_customers') },
      {},
    )
    const seeds = tree.children.get('seeds')!
    const leaf = seeds.children.get('raw_customers')!
    expect(leaf.uniqueId).toBe('seed.project.raw_customers')
    expect(leaf.resourceType).toBe('seed')
  })

  it('omits empty sections', () => {
    const tree = buildTree(
      { 'model.project.a': makeModel('a') },
      {},
      {},
      {},
      {},
    )
    expect([...tree.children.keys()]).toEqual(['models'])
  })

  it('orders sections as models, snapshots, seeds, sources, exposures', () => {
    const tree = buildTree(
      { 'model.project.a': makeModel('a') },
      { 'source.project.raw.c': makeSource('c') },
      { 'exposure.project.dash': makeExposure('dash') },
      { 'seed.project.b': makeSeed('b') },
      { 'snapshot.project.s': makeSnapshot('s') },
    )
    expect([...tree.children.keys()]).toEqual([
      'models',
      'snapshots',
      'seeds',
      'sources',
      'exposures',
    ])
  })

  it('carries tags onto snapshot and seed leaves for tag filtering', () => {
    const tree = buildTree(
      {},
      {},
      {},
      { 'seed.project.b': makeSeed('b', 'seeds/b.csv', ['static']) },
      { 'snapshot.project.s': makeSnapshot('s', 'snapshots/s.sql', ['scd2']) },
    )
    expect(tree.children.get('snapshots')!.children.get('s')!.tags).toEqual(['scd2'])
    expect(tree.children.get('seeds')!.children.get('b')!.tags).toEqual(['static'])
  })

  it('groups sources by source_name', () => {
    const tree = buildTree(
      {},
      {
        'source.project.raw.orders': makeSource('orders', 'raw'),
        'source.project.crm.contacts': makeSource('contacts', 'crm'),
      },
      {},
    )
    const sources = tree.children.get('sources')!
    expect([...sources.children.keys()].sort()).toEqual(['crm', 'raw'])
  })
})

describe('collectFolderPaths', () => {
  it('collects section and nested folder paths but not leaves', () => {
    const tree = buildTree(
      { 'model.project.stg_orders': makeModel('stg_orders', 'models/staging/stg_orders.sql') },
      {},
      {},
      {},
      { 'snapshot.project.s': makeSnapshot('s') },
    )
    const paths = collectFolderPaths(tree)
    expect(paths).toContain('models')
    expect(paths).toContain('models/staging')
    expect(paths).toContain('snapshots')
    expect(paths).not.toContain('snapshot.project.s')
  })
})
