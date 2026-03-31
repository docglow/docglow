import type { DocglowModel, DocglowSource } from '../types'

export interface SidebarTreeNode {
  name: string
  path: string
  uniqueId?: string
  resourceType?: string
  tags?: readonly string[]
  children: Map<string, SidebarTreeNode>
}

/** Collect and deduplicate all tags from models and sources, sorted alphabetically. */
export function collectAllTags(
  models: Record<string, DocglowModel>,
  sources: Record<string, DocglowSource>,
): string[] {
  const tags = new Set<string>()
  for (const m of Object.values(models)) {
    for (const t of m.tags) tags.add(t)
  }
  for (const s of Object.values(sources)) {
    for (const t of s.tags) tags.add(t)
  }
  return [...tags].sort()
}

/** Returns true if a node (or any descendant) matches the selected tags. */
export function nodeMatchesTags(
  node: SidebarTreeNode,
  selected: ReadonlySet<string>,
  mode: 'include' | 'exclude',
): boolean {
  // Leaf node with tags
  if (node.uniqueId && node.tags) {
    const hasMatch = node.tags.some(t => selected.has(t))
    return mode === 'include' ? hasMatch : !hasMatch
  }
  // Folder: matches if any child matches
  for (const child of node.children.values()) {
    if (nodeMatchesTags(child, selected, mode)) return true
  }
  return false
}
