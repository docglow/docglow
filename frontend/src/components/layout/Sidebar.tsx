import { useState, useMemo, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'
import { useTagFilterStore } from '../../stores/tagFilterStore'
import type { DocglowModel, DocglowSource } from '../../types'

interface TreeNode {
  name: string
  path: string
  uniqueId?: string
  resourceType?: string
  tags?: readonly string[]
  children: Map<string, TreeNode>
}

function buildTree(
  models: Record<string, DocglowModel>,
  sources: Record<string, DocglowSource>,
): TreeNode {
  const root: TreeNode = { name: 'root', path: '', children: new Map() }

  // Add models organized by folder
  const modelRoot: TreeNode = { name: 'models', path: 'models', children: new Map() }
  for (const model of Object.values(models)) {
    const parts = model.path.replace(/^models\//, '').split('/')
    parts.pop() // remove filename
    let current = modelRoot
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
    current.children.set(model.name, {
      name: model.name,
      path: model.unique_id,
      uniqueId: model.unique_id,
      resourceType: 'model',
      tags: model.tags,
      children: new Map(),
    })
  }
  if (modelRoot.children.size > 0) root.children.set('models', modelRoot)

  // Add sources grouped by source_name
  const sourceRoot: TreeNode = { name: 'sources', path: 'sources', children: new Map() }
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

  return root
}

function collectFolderPaths(node: TreeNode): string[] {
  const paths: string[] = []
  if (node.children.size > 0 && !node.uniqueId) {
    paths.push(node.path)
    for (const child of node.children.values()) {
      paths.push(...collectFolderPaths(child))
    }
  }
  return paths
}

function collectAllTags(
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
function nodeMatchesTags(
  node: TreeNode,
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

interface TreeItemProps {
  node: TreeNode
  depth?: number
  expandedPaths: Set<string>
  onToggle: (path: string) => void
  tagSelected: ReadonlySet<string>
  tagMode: 'include' | 'exclude'
}

function TreeItem({ node, depth = 0, expandedPaths, onToggle, tagSelected, tagMode }: TreeItemProps) {
  const navigate = useNavigate()
  const { id } = useParams()
  const isLeaf = node.children.size === 0
  const isActive = node.uniqueId && id === encodeURIComponent(node.uniqueId)
  const expanded = expandedPaths.has(node.path)
  const hasTagFilter = tagSelected.size > 0

  const sortedChildren = useMemo(() => {
    const entries = [...node.children.entries()]
      .filter(([, child]) => !hasTagFilter || nodeMatchesTags(child, tagSelected, tagMode))
      .sort(([, a], [, b]) => {
        const aIsFolder = a.children.size > 0 && !a.uniqueId
        const bIsFolder = b.children.size > 0 && !b.uniqueId
        if (aIsFolder && !bIsFolder) return -1
        if (!aIsFolder && bIsFolder) return 1
        return a.name.localeCompare(b.name)
      })
    return entries
  }, [node.children, hasTagFilter, tagSelected, tagMode])

  if (isLeaf && node.uniqueId) {
    return (
      <button
        onClick={() => navigate(`/${node.resourceType}/${encodeURIComponent(node.uniqueId!)}`)}
        className={`w-full text-left px-2 py-1 text-sm rounded hover:bg-[var(--bg-surface)]
                    transition-colors cursor-pointer truncate
                    ${isActive ? 'bg-primary/10 text-primary font-medium' : 'text-[var(--text)]'}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        title={node.name}
      >
        {node.name}
      </button>
    )
  }

  return (
    <div>
      <button
        onClick={() => onToggle(node.path)}
        className="w-full text-left px-2 py-1 text-sm font-medium rounded
                   hover:bg-[var(--bg-surface)] transition-colors cursor-pointer
                   flex items-center gap-1 text-[var(--text)]"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        <svg
          className={`w-3 h-3 transition-transform shrink-0 ${expanded ? 'rotate-90' : ''}`}
          fill="currentColor" viewBox="0 0 20 20"
        >
          <path fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd" />
        </svg>
        <span className="truncate">{node.name}</span>
        <span className="ml-auto text-xs text-[var(--text-muted)]">
          {sortedChildren.length}
        </span>
      </button>
      {expanded && (
        <div>
          {sortedChildren.map(([key, child]) => (
            <TreeItem key={key} node={child} depth={depth + 1} expandedPaths={expandedPaths} onToggle={onToggle} tagSelected={tagSelected} tagMode={tagMode} />
          ))}
        </div>
      )}
    </div>
  )
}

export function Sidebar() {
  const { data } = useProjectStore()
  const navigate = useNavigate()
  const { selected: tagSelected, mode: tagMode, toggle: toggleTag, clear: clearTags } = useTagFilterStore()

  const tree = useMemo(() => {
    if (!data) return null
    return buildTree(data.models, data.sources)
  }, [data])

  const allTags = useMemo(() => {
    if (!data) return []
    return collectAllTags(data.models, data.sources)
  }, [data])

  // Only "models" expanded by default; sub-folders collapsed
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => new Set(['models']))

  const allFolderPaths = useMemo(() => {
    if (!tree) return []
    return collectFolderPaths(tree)
  }, [tree])

  const togglePath = useCallback((path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }, [])

  const expandAll = useCallback(() => {
    setExpandedPaths(new Set(allFolderPaths))
  }, [allFolderPaths])

  const collapseAll = useCallback(() => {
    setExpandedPaths(new Set())
  }, [])

  const modelCount = data ? Object.keys(data.models).length : 0
  const sourceCount = data ? Object.keys(data.sources).length : 0

  const filteredModelCount = useMemo(() => {
    if (!data || tagSelected.size === 0) return modelCount
    return Object.values(data.models).filter(m => {
      const hasMatch = m.tags.some(t => tagSelected.has(t))
      return tagMode === 'include' ? hasMatch : !hasMatch
    }).length
  }, [data, tagSelected, tagMode, modelCount])

  if (!tree) return null

  return (
    <aside className="w-full h-full border-r border-[var(--border)] bg-[var(--bg)] overflow-y-auto flex flex-col">
      <div className="flex items-center justify-end gap-1 px-2 pt-2 pb-1">
        <button
          onClick={expandAll}
          className="px-1.5 py-0.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)]
                     hover:bg-[var(--bg-surface)] rounded transition-colors cursor-pointer"
          title="Expand All"
        >
          Expand All
        </button>
        <span className="text-[var(--text-muted)] text-xs">/</span>
        <button
          onClick={collapseAll}
          className="px-1.5 py-0.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)]
                     hover:bg-[var(--bg-surface)] rounded transition-colors cursor-pointer"
          title="Collapse All"
        >
          Collapse All
        </button>
      </div>

      {/* Tag filter chips */}
      {allTags.length > 0 && (
        <div className="px-2 pb-2 border-b border-[var(--border)]">
          <div className="flex items-center gap-1 mb-1.5">
            <svg className="w-3 h-3 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
            </svg>
            <span className="text-xs font-medium text-[var(--text-muted)]">Tags</span>
            {tagSelected.size > 0 && (
              <button
                onClick={clearTags}
                className="ml-auto text-xs text-danger hover:text-danger/80 cursor-pointer transition-colors"
                title="Clear tag filter"
              >
                Clear
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {allTags.map(tag => {
              const isActive = tagSelected.has(tag)
              return (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={`px-2 py-0.5 text-xs rounded-full cursor-pointer transition-colors
                    ${isActive
                      ? 'bg-primary text-white'
                      : 'bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text)] border border-[var(--border)]'
                    }`}
                >
                  {tag}
                </button>
              )
            })}
          </div>
        </div>
      )}

      <nav className="py-2 flex-1">
        {[...tree.children.entries()].map(([key, node]) => (
          <TreeItem key={key} node={node} depth={0} expandedPaths={expandedPaths} onToggle={togglePath} tagSelected={tagSelected} tagMode={tagMode} />
        ))}

        <div className="mt-3 pt-3 border-t border-[var(--border)] px-2">
          <button
            onClick={() => navigate('/lineage')}
            className="w-full text-left px-2 py-1.5 text-sm rounded
                       hover:bg-[var(--bg-surface)] transition-colors cursor-pointer
                       flex items-center gap-2 text-[var(--text)]"
          >
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Lineage
          </button>
          <button
            onClick={() => navigate('/health')}
            className="w-full text-left px-2 py-1.5 text-sm rounded
                       hover:bg-[var(--bg-surface)] transition-colors cursor-pointer
                       flex items-center gap-2 text-[var(--text)]"
          >
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Health
            {data && (
              <span className={`ml-auto text-xs font-medium ${
                data.health.score.grade === 'A' ? 'text-success' :
                data.health.score.grade === 'B' ? 'text-primary' :
                data.health.score.grade === 'C' ? 'text-warning' : 'text-danger'
              }`}>
                {data.health.score.grade}
              </span>
            )}
          </button>
          <button
            onClick={() => navigate('/layers')}
            className="w-full text-left px-2 py-1.5 text-sm rounded
                       hover:bg-[var(--bg-surface)] transition-colors cursor-pointer
                       flex items-center gap-2 text-[var(--text)]"
          >
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            Layers
          </button>
        </div>
      </nav>

      <div className="p-3 border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
        {tagSelected.size > 0
          ? <>{filteredModelCount} of {modelCount} models &middot; {sourceCount} sources</>
          : <>{modelCount} models &middot; {sourceCount} sources</>
        }
      </div>
    </aside>
  )
}
