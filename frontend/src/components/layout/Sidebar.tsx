import { useState, useMemo, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'
import { useTagFilterStore } from '../../stores/tagFilterStore'
import { collectAllTags, nodeMatchesTags, type SidebarTreeNode } from '../../utils/sidebarFilters'
import { buildTree, collectFolderPaths } from '../../utils/sidebarTree'
import { failingTestCount } from '../../utils/testStatus'
import { buildResourcePath } from '../../utils/resourceRoutes'

type TreeNode = SidebarTreeNode

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
        onClick={() => navigate(buildResourcePath(node.uniqueId!))}
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
    return buildTree(data.models, data.sources, data.exposures, data.seeds, data.snapshots)
  }, [data])

  const allTags = useMemo(() => {
    if (!data) return []
    return collectAllTags(data.models, data.sources, data.exposures, data.seeds, data.snapshots)
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

  const exposureCount = data ? Object.keys(data.exposures).length : 0
  const seedCount = data ? Object.keys(data.seeds).length : 0
  const snapshotCount = data ? Object.keys(data.snapshots).length : 0

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
            onClick={() => navigate('/erd')}
            className="w-full text-left px-2 py-1.5 text-sm rounded
                       hover:bg-[var(--bg-surface)] transition-colors cursor-pointer
                       flex items-center gap-2 text-[var(--text)]"
          >
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <rect x="3" y="4" width="7" height="6" rx="1" strokeWidth={1.75} />
              <rect x="14" y="4" width="7" height="6" rx="1" strokeWidth={1.75} />
              <rect x="3" y="14" width="7" height="6" rx="1" strokeWidth={1.75} />
              <rect x="14" y="14" width="7" height="6" rx="1" strokeWidth={1.75} />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M10 7h4M10 17h4M6.5 10v4M17.5 10v4" />
            </svg>
            ERD
          </button>
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
            onClick={() => navigate('/tests')}
            className="w-full text-left px-2 py-1.5 text-sm rounded
                       hover:bg-[var(--bg-surface)] transition-colors cursor-pointer
                       flex items-center gap-2 text-[var(--text)]"
          >
            <svg className="w-4 h-4 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            Tests
            {data?.tests && (() => {
              const failing = failingTestCount(data.tests.summary)
              return failing > 0 ? (
                <span className="ml-auto text-xs font-medium text-danger">{failing}</span>
              ) : data.tests.summary.total > 0 ? (
                <span className="ml-auto text-xs font-medium text-success">✓</span>
              ) : null
            })()}
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
          ? <>{filteredModelCount} of {modelCount} models &middot; {sourceCount} sources &middot; {exposureCount} exposures</>
          : <>{modelCount} models &middot; {sourceCount} sources &middot; {exposureCount} exposures</>
        }
        {snapshotCount > 0 && <> &middot; {snapshotCount} snapshots</>}
        {seedCount > 0 && <> &middot; {seedCount} seeds</>}
      </div>
    </aside>
  )
}
