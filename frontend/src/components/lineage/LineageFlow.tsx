import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  MarkerType,
  Position,
  type Node,
  type Edge,
  type NodeTypes,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import { useNavigate } from 'react-router-dom'
import type { LineageNode, LineageEdge } from '../../types'
import { getFullChain } from '../../utils/graphTraversal'
import { DagNode } from './DagNode'
import { FolderNode } from './FolderNode'

const NODE_WIDTH = 180
const NODE_HEIGHT = 44
const FOLDER_NODE_WIDTH = 220
const FOLDER_NODE_HEIGHT = 60

const RESOURCE_COLORS: Record<string, string> = {
  model: '#2563eb',
  source: '#16a34a',
  seed: '#6b7280',
  snapshot: '#7c3aed',
  exposure: '#d97706',
  metric: '#7c3aed',
}

const nodeTypes: NodeTypes = {
  dag: DagNode,
  folder: FolderNode,
}

interface LayoutItem {
  id: string
  x: number
  y: number
  width: number
  height: number
  data: LineageNode
  isFolder: boolean
}

interface LayoutResult {
  nodes: LayoutItem[]
  edges: Array<{ source: string; target: string }>
}

function computeLayout(
  nodes: LineageNode[],
  edges: LineageEdge[],
  folderNodeIds: Set<string>,
): LayoutResult {
  if (nodes.length === 0) return { nodes: [], edges: [] }

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 20, ranksep: 60, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) {
    const isFolder = folderNodeIds.has(node.id)
    g.setNode(node.id, {
      width: isFolder ? FOLDER_NODE_WIDTH : NODE_WIDTH,
      height: isFolder ? FOLDER_NODE_HEIGHT : NODE_HEIGHT,
    })
  }

  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target)
    }
  }

  dagre.layout(g)

  const layoutNodes: LayoutItem[] = nodes.map((node) => {
    const isFolder = folderNodeIds.has(node.id)
    const w = isFolder ? FOLDER_NODE_WIDTH : NODE_WIDTH
    const h = isFolder ? FOLDER_NODE_HEIGHT : NODE_HEIGHT
    const pos = g.node(node.id)
    return {
      id: node.id,
      x: pos.x - w / 2,
      y: pos.y - h / 2,
      width: w,
      height: h,
      data: node,
      isFolder,
    }
  })

  const layoutEdges = edges.filter(
    (e) => g.hasNode(e.source) && g.hasNode(e.target)
  )

  return { nodes: layoutNodes, edges: layoutEdges }
}

export interface LineageFlowProps {
  nodes: LineageNode[]
  edges: LineageEdge[]
  highlightId?: string
  onNodeClick?: (id: string) => void
  /** Map of folder node id → { modelCount, sourceCount } for folder rendering */
  folderData?: Record<string, { modelCount: number; sourceCount: number }>
  /** Set of currently expanded folder ids */
  expandedFolders?: Set<string>
  /** Called when a folder node is clicked */
  onFolderClick?: (folderId: string) => void
}

function LineageFlowInner({
  nodes,
  edges,
  highlightId,
  onNodeClick,
  folderData,
  expandedFolders,
  onFolderClick,
}: LineageFlowProps) {
  const navigate = useNavigate()
  const { fitView, getNodes } = useReactFlow()
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const centerOnHighlight = useCallback(() => {
    if (!highlightId) return
    const target = getNodes().find(n => n.id === highlightId)
    if (!target) return
    fitView({ nodes: [target], duration: 300, padding: 0.5 })
  }, [highlightId, fitView, getNodes])

  const folderNodeIds = useMemo(
    () => new Set(Object.keys(folderData ?? {})),
    [folderData],
  )

  const layout = useMemo(
    () => computeLayout(nodes, edges, folderNodeIds),
    [nodes, edges, folderNodeIds],
  )

  // Highlighting
  const activeId = hoveredId ?? highlightId ?? null
  const highlightedSet = useMemo(() => {
    if (!activeId) return null
    return getFullChain(activeId, edges)
  }, [activeId, edges])

  // Build React Flow nodes
  const rfNodes = useMemo((): Node[] => {
    return layout.nodes.map((ln) => {
      if (ln.isFolder) {
        const meta = folderData?.[ln.id]
        return {
          id: ln.id,
          type: 'folder',
          position: { x: ln.x, y: ln.y },
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
          data: {
            name: ln.data.name,
            modelCount: meta?.modelCount ?? 0,
            sourceCount: meta?.sourceCount ?? 0,
            isExpanded: expandedFolders?.has(ln.id) ?? false,
          },
          style: {
            opacity: !highlightedSet || highlightedSet.has(ln.id) ? 1 : 0.4,
            transition: 'opacity 0.15s ease',
          },
        }
      }

      return {
        id: ln.id,
        type: 'dag',
        position: { x: ln.x, y: ln.y },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: {
          name: ln.data.name,
          resource_type: ln.data.resource_type,
          materialization: ln.data.materialization,
          test_status: ln.data.test_status,
          isActive: ln.id === activeId,
        },
        style: {
          opacity: !highlightedSet || highlightedSet.has(ln.id) ? 1 : 0.4,
          transition: 'opacity 0.15s ease',
        },
      }
    })
  }, [layout.nodes, highlightedSet, activeId, folderData, expandedFolders])

  // Build React Flow edges
  const rfEdges = useMemo((): Edge[] => {
    return layout.edges.map((e) => {
      const isHighlighted = highlightedSet
        ? highlightedSet.has(e.source) && highlightedSet.has(e.target)
        : false
      return {
        id: `${e.source}__${e.target}`,
        source: e.source,
        target: e.target,
        type: 'smoothstep',
        animated: false,
        style: {
          stroke: isHighlighted ? '#2563eb' : 'var(--text-muted, #94a3b8)',
          strokeWidth: isHighlighted ? 2 : 1.5,
          opacity: !highlightedSet ? 0.5 : isHighlighted ? 0.8 : 0.15,
          transition: 'opacity 0.15s ease, stroke 0.15s ease',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isHighlighted ? '#2563eb' : '#94a3b8',
          width: 16,
          height: 12,
        },
      }
    })
  }, [layout.edges, highlightedSet])

  // Fit view when data changes
  useEffect(() => {
    if (layout.nodes.length > 0) {
      requestAnimationFrame(() => fitView({ padding: 0.1 }))
    }
  }, [layout.nodes.length, layout.edges.length, fitView])

  const handleNodeMouseEnter: NodeMouseHandler = useCallback((_, node) => {
    setHoveredId(node.id)
  }, [])

  const handleNodeMouseLeave: NodeMouseHandler = useCallback(() => {
    setHoveredId(null)
  }, [])

  const handleNodeClick: NodeMouseHandler = useCallback((_, node) => {
    // Folder node click → toggle expand
    if (node.id.startsWith('folder:') && onFolderClick) {
      onFolderClick(node.id)
      return
    }

    if (onNodeClick) {
      onNodeClick(node.id)
      return
    }
    const type = node.id.startsWith('source.') ? 'source' : 'model'
    navigate(`/${type}/${encodeURIComponent(node.id)}`)
  }, [navigate, onNodeClick, onFolderClick])

  if (nodes.length === 0) {
    return <div className="text-[var(--text-muted)] text-sm">No lineage data available.</div>
  }

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      onNodeMouseEnter={handleNodeMouseEnter}
      onNodeMouseLeave={handleNodeMouseLeave}
      onNodeClick={handleNodeClick}
      nodesDraggable={false}
      nodesConnectable={false}
      fitView
      minZoom={0.05}
      maxZoom={3}
    >
      <Controls showInteractive={false} />
      {highlightId && (
        <div className="react-flow__panel bottom-left" style={{ left: 10, bottom: 110 }}>
          <button
            onClick={centerOnHighlight}
            title="Center on selected model"
            className="react-flow__controls-button"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 26,
              height: 26,
              borderRadius: 4,
              border: '1px solid var(--border, #e2e8f0)',
              background: 'var(--bg, #fff)',
              cursor: 'pointer',
              color: '#f59e0b',
            }}
          >
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <circle cx={12} cy={12} r={3} />
              <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
            </svg>
          </button>
        </div>
      )}
      <MiniMap
        nodeColor={(node) => {
          if (node.id.startsWith('folder:')) return '#64748b'
          return RESOURCE_COLORS[(node.data as Record<string, unknown>)?.resource_type as string] ?? '#6b7280'
        }}
        maskColor="rgba(0,0,0,0.08)"
        pannable
        zoomable
      />
    </ReactFlow>
  )
}

export function LineageFlow(props: LineageFlowProps) {
  return (
    <ReactFlowProvider>
      <LineageFlowInner {...props} />
    </ReactFlowProvider>
  )
}
