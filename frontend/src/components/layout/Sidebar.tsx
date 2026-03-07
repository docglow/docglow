import { useState, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'
import type { DatumModel, DatumSource } from '../../types'

interface TreeNode {
  name: string
  path: string
  uniqueId?: string
  resourceType?: string
  children: Map<string, TreeNode>
}

function buildTree(
  models: Record<string, DatumModel>,
  sources: Record<string, DatumSource>,
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
      children: new Map(),
    })
  }
  if (sourceRoot.children.size > 0) root.children.set('sources', sourceRoot)

  return root
}

function TreeItem({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const navigate = useNavigate()
  const { id } = useParams()
  const isLeaf = node.children.size === 0
  const isActive = node.uniqueId && id === encodeURIComponent(node.uniqueId)

  const sortedChildren = useMemo(() => {
    return [...node.children.entries()].sort(([, a], [, b]) => {
      const aIsFolder = a.children.size > 0 && !a.uniqueId
      const bIsFolder = b.children.size > 0 && !b.uniqueId
      if (aIsFolder && !bIsFolder) return -1
      if (!aIsFolder && bIsFolder) return 1
      return a.name.localeCompare(b.name)
    })
  }, [node.children])

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
        onClick={() => setExpanded(!expanded)}
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
          {node.children.size}
        </span>
      </button>
      {expanded && (
        <div>
          {sortedChildren.map(([key, child]) => (
            <TreeItem key={key} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export function Sidebar() {
  const { data } = useProjectStore()
  const navigate = useNavigate()

  const tree = useMemo(() => {
    if (!data) return null
    return buildTree(data.models, data.sources)
  }, [data])

  if (!tree) return null

  const modelCount = data ? Object.keys(data.models).length : 0
  const sourceCount = data ? Object.keys(data.sources).length : 0

  return (
    <aside className="w-64 border-r border-[var(--border)] bg-[var(--bg)] overflow-y-auto shrink-0 flex flex-col">
      <nav className="py-2 flex-1">
        {[...tree.children.entries()].map(([key, node]) => (
          <TreeItem key={key} node={node} depth={0} />
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
        </div>
      </nav>

      <div className="p-3 border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
        {modelCount} models &middot; {sourceCount} sources
      </div>
    </aside>
  )
}
