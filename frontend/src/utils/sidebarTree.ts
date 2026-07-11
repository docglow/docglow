import type { DocglowExposure, DocglowModel, DocglowSource } from '../types'
import type { SidebarTreeNode } from './sidebarFilters'

/**
 * Add a folder-structured section (models, snapshots, seeds) to the tree.
 * Items are placed under sub-folders derived from their file path, with the
 * top-level directory prefix (e.g. `models/`, `snapshots/`) stripped.
 */
function addFolderSection(
  root: SidebarTreeNode,
  sectionName: string,
  items: Record<string, DocglowModel>,
  resourceType: string,
): void {
  const sectionRoot: SidebarTreeNode = { name: sectionName, path: sectionName, children: new Map() }
  const prefix = `${sectionName}/`
  for (const item of Object.values(items)) {
    const relative = item.path.startsWith(prefix) ? item.path.slice(prefix.length) : item.path
    const parts = relative.split('/')
    parts.pop() // remove filename
    let current = sectionRoot
    for (const part of parts) {
      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          path: `${current.path}/${part}`,
          children: new Map(),
        })
      }
      current = current.children.get(part)!
    }
    current.children.set(item.name, {
      name: item.name,
      path: item.unique_id,
      uniqueId: item.unique_id,
      resourceType,
      tags: item.tags,
      children: new Map(),
    })
  }
  if (sectionRoot.children.size > 0) root.children.set(sectionName, sectionRoot)
}

export function buildTree(
  models: Record<string, DocglowModel>,
  sources: Record<string, DocglowSource>,
  exposures: Record<string, DocglowExposure>,
  seeds: Record<string, DocglowModel> = {},
  snapshots: Record<string, DocglowModel> = {},
): SidebarTreeNode {
  const root: SidebarTreeNode = { name: 'root', path: '', children: new Map() }

  addFolderSection(root, 'models', models, 'model')
  addFolderSection(root, 'snapshots', snapshots, 'snapshot')
  addFolderSection(root, 'seeds', seeds, 'seed')

  // Add sources grouped by source_name
  const sourceRoot: SidebarTreeNode = { name: 'sources', path: 'sources', children: new Map() }
  for (const source of Object.values(sources)) {
    if (!sourceRoot.children.has(source.source_name)) {
      sourceRoot.children.set(source.source_name, {
        name: source.source_name,
        path: `sources/${source.source_name}`,
        children: new Map(),
      })
    }
    const sourceGroup = sourceRoot.children.get(source.source_name)!
    sourceGroup.children.set(source.name, {
      name: source.name,
      path: source.unique_id,
      uniqueId: source.unique_id,
      resourceType: 'source',
      tags: source.tags,
      children: new Map(),
    })
  }
  if (sourceRoot.children.size > 0) root.children.set('sources', sourceRoot)

  const exposureRoot: SidebarTreeNode = { name: 'exposures', path: 'exposures', children: new Map() }
  for (const exposure of Object.values(exposures)) {
    exposureRoot.children.set(exposure.name, {
      name: exposure.name,
      path: exposure.unique_id,
      uniqueId: exposure.unique_id,
      resourceType: 'exposure',
      tags: exposure.tags,
      children: new Map(),
    })
  }
  if (exposureRoot.children.size > 0) root.children.set('exposures', exposureRoot)

  return root
}

export function collectFolderPaths(node: SidebarTreeNode): string[] {
  const paths: string[] = []
  if (node.children.size > 0 && !node.uniqueId) {
    paths.push(node.path)
    for (const child of node.children.values()) {
      paths.push(...collectFolderPaths(child))
    }
  }
  return paths
}
