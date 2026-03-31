import { describe, it, expect } from 'vitest'
import { collectAllTags, nodeMatchesTags, type SidebarTreeNode } from '../utils/sidebarFilters'
import type { DocglowModel, DocglowSource } from '../types'

function makeModel(name: string, tags: string[]): DocglowModel {
  return {
    unique_id: `model.project.${name}`,
    name,
    description: '',
    path: `models/${name}.sql`,
    original_file_path: `models/${name}.sql`,
    schema: 'public',
    database: 'db',
    materialization: 'view',
    columns: [],
    tags,
    test_results: [],
    depends_on: [],
    referenced_by: [],
    config: {},
    meta: {},
  } as unknown as DocglowModel
}

function makeSource(name: string, tags: string[]): DocglowSource {
  return {
    unique_id: `source.project.${name}`,
    name,
    source_name: 'raw',
    description: '',
    schema: 'public',
    database: 'db',
    columns: [],
    tags,
    meta: {},
  } as unknown as DocglowSource
}

function makeLeaf(name: string, tags: string[]): SidebarTreeNode {
  return {
    name,
    path: `model.project.${name}`,
    uniqueId: `model.project.${name}`,
    resourceType: 'model',
    tags,
    children: new Map(),
  }
}

function makeFolder(name: string, children: SidebarTreeNode[]): SidebarTreeNode {
  const childMap = new Map<string, SidebarTreeNode>()
  for (const c of children) childMap.set(c.name, c)
  return {
    name,
    path: `models/${name}`,
    children: childMap,
  }
}

describe('collectAllTags', () => {
  it('collects tags from models and sources', () => {
    const models = {
      'model.project.a': makeModel('a', ['finance', 'daily']),
      'model.project.b': makeModel('b', ['marketing']),
    }
    const sources = {
      'source.project.c': makeSource('c', ['raw', 'daily']),
    }

    const tags = collectAllTags(models, sources)
    expect(tags).toEqual(['daily', 'finance', 'marketing', 'raw'])
  })

  it('deduplicates tags across models and sources', () => {
    const models = {
      'model.project.a': makeModel('a', ['shared']),
    }
    const sources = {
      'source.project.b': makeSource('b', ['shared']),
    }

    const tags = collectAllTags(models, sources)
    expect(tags).toEqual(['shared'])
  })

  it('returns empty array when no tags exist', () => {
    const models = {
      'model.project.a': makeModel('a', []),
    }
    const tags = collectAllTags(models, {})
    expect(tags).toEqual([])
  })

  it('returns sorted tags', () => {
    const models = {
      'model.project.a': makeModel('a', ['zebra', 'alpha']),
    }
    const tags = collectAllTags(models, {})
    expect(tags).toEqual(['alpha', 'zebra'])
  })
})

describe('nodeMatchesTags', () => {
  describe('include mode', () => {
    it('matches a leaf node that has a selected tag', () => {
      const node = makeLeaf('revenue', ['finance', 'daily'])
      expect(nodeMatchesTags(node, new Set(['finance']), 'include')).toBe(true)
    })

    it('does not match a leaf node without any selected tag', () => {
      const node = makeLeaf('revenue', ['marketing'])
      expect(nodeMatchesTags(node, new Set(['finance']), 'include')).toBe(false)
    })

    it('does not match a leaf node with empty tags', () => {
      const node = makeLeaf('revenue', [])
      expect(nodeMatchesTags(node, new Set(['finance']), 'include')).toBe(false)
    })

    it('matches a folder if any child matches', () => {
      const folder = makeFolder('staging', [
        makeLeaf('a', ['finance']),
        makeLeaf('b', ['marketing']),
      ])
      expect(nodeMatchesTags(folder, new Set(['finance']), 'include')).toBe(true)
    })

    it('does not match a folder if no children match', () => {
      const folder = makeFolder('staging', [
        makeLeaf('a', ['marketing']),
        makeLeaf('b', ['marketing']),
      ])
      expect(nodeMatchesTags(folder, new Set(['finance']), 'include')).toBe(false)
    })

    it('matches nested folders if a deep child matches', () => {
      const inner = makeFolder('inner', [
        makeLeaf('deep', ['finance']),
      ])
      const outer = makeFolder('outer', [inner])
      expect(nodeMatchesTags(outer, new Set(['finance']), 'include')).toBe(true)
    })

    it('does not match empty folders', () => {
      const folder = makeFolder('empty', [])
      expect(nodeMatchesTags(folder, new Set(['finance']), 'include')).toBe(false)
    })
  })

  describe('exclude mode', () => {
    it('matches a leaf node that does NOT have the selected tag', () => {
      const node = makeLeaf('revenue', ['marketing'])
      expect(nodeMatchesTags(node, new Set(['finance']), 'exclude')).toBe(true)
    })

    it('does not match a leaf node that has the selected tag', () => {
      const node = makeLeaf('revenue', ['finance'])
      expect(nodeMatchesTags(node, new Set(['finance']), 'exclude')).toBe(false)
    })

    it('matches a leaf with empty tags (no tag to exclude)', () => {
      const node = makeLeaf('revenue', [])
      expect(nodeMatchesTags(node, new Set(['finance']), 'exclude')).toBe(true)
    })

    it('matches folder if any child survives exclusion', () => {
      const folder = makeFolder('staging', [
        makeLeaf('a', ['finance']),   // excluded
        makeLeaf('b', ['marketing']), // survives
      ])
      expect(nodeMatchesTags(folder, new Set(['finance']), 'exclude')).toBe(true)
    })

    it('does not match folder if all children are excluded', () => {
      const folder = makeFolder('staging', [
        makeLeaf('a', ['finance']),
        makeLeaf('b', ['finance', 'daily']),
      ])
      expect(nodeMatchesTags(folder, new Set(['finance']), 'exclude')).toBe(false)
    })
  })

  describe('multiple selected tags', () => {
    it('include mode uses OR — matches if node has ANY selected tag', () => {
      const node = makeLeaf('a', ['finance'])
      expect(nodeMatchesTags(node, new Set(['finance', 'marketing']), 'include')).toBe(true)
    })

    it('exclude mode excludes if node has ANY selected tag', () => {
      const node = makeLeaf('a', ['finance'])
      expect(nodeMatchesTags(node, new Set(['finance', 'marketing']), 'exclude')).toBe(false)
    })
  })
})
