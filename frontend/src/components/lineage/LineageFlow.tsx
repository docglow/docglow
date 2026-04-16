import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  type NodeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import { useNavigate } from 'react-router-dom'
import type { LineageNode, LineageEdge, LayerDefinition, ColumnLineageData } from '../../types'
import { getUnionChain } from '../../utils/graphTraversal'
import { useColumnHighlightStore } from '../../stores/columnHighlightStore'
import { buildReverseIndex, getColumnTraceResult } from '../../utils/columnLineageGraph'
import { DagNode } from './DagNode'
import { FolderNode } from './FolderNode'

const NODE_WIDTH = 180
const NODE_HEIGHT = 44
const FOLDER_NODE_WIDTH = 220
const FOLDER_NODE_HEIGHT = 60
const HIGHLIGHT_DEPTH_CAP = 4

const RESOURCE_COLORS: Record<string, string> = {
  model: '#2563eb',
  source: '#16a34a',
  seed: '#6b7280',
  snapshot: '#7c3aed',
  exposure: '#d97706',
  metric: '#7c3aed',
}

function LayerBandNode({ data }: { data: { label: string; color: string; width: number; height: number } }) {
  return (
    <div
      style={{
        width: data.width,
        height: data.height,
        position: 'relative',
        pointerEvents: 'none',
      }}
    >
      {/* Background — low opacity */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: data.color,
          opacity: 0.18,
          borderRadius: 8,
        }}
      />
      {/* Label — independent opacity so it's readable */}
      <span
        style={{
          position: 'absolute',
          top: 6,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 11,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'var(--text-muted, #64748b)',
          opacity: 0.7,
          whiteSpace: 'nowrap',
        }}
      >
        {data.label}
      </span>
    </div>
  )
}

const nodeTypes: NodeTypes = {
  dag: DagNode,
  folder: FolderNode,
  layerBand: LayerBandNode,
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

const COLUMN_ROW_HEIGHT = 22
const MAX_VISIBLE_COLUMNS_LAYOUT = 20

function computeLayout(
  nodes: LineageNode[],
  edges: LineageEdge[],
  folderNodeIds: Set<string>,
  expandedNodeIds?: Set<string>,
  modelColumns?: Record<string, string[]>,
): LayoutResult {
  if (nodes.length === 0) return { nodes: [], edges: [] }

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 20, ranksep: 60, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) {
    const isFolder = folderNodeIds.has(node.id)
    let nodeHeight = NODE_HEIGHT
    if (!isFolder && expandedNodeIds?.has(node.id)) {
      const colCount = modelColumns?.[node.id]?.length ?? 0
      if (colCount > 0) {
        const visibleCols = Math.min(colCount, MAX_VISIBLE_COLUMNS_LAYOUT)
        nodeHeight = NODE_HEIGHT + visibleCols * COLUMN_ROW_HEIGHT + 4
      }
    }
    g.setNode(node.id, {
      width: isFolder ? FOLDER_NODE_WIDTH : NODE_WIDTH,
      height: isFolder ? FOLDER_NODE_HEIGHT : nodeHeight,
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
    const h = isFolder ? FOLDER_NODE_HEIGHT : (g.node(node.id)?.height ?? NODE_HEIGHT)
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

  // Post-layout: align nodes by layer rank into consistent vertical columns.
  // Only apply when multiple distinct layers are visible — if all nodes share
  // a single layer, dagre's natural left-to-right layout is already optimal.
  const distinctLayers = new Set(nodes.map(n => n.layer).filter(l => l != null))
  if (distinctLayers.size >= 2) {
    // Compute average x-center per layer
    const layerXSums = new Map<number, { sum: number; count: number }>()
    for (const ln of layoutNodes) {
      const layer = ln.data.layer
      if (layer == null) continue
      const center = ln.x + ln.width / 2
      const entry = layerXSums.get(layer)
      if (entry) {
        entry.sum += center
        entry.count += 1
      } else {
        layerXSums.set(layer, { sum: center, count: 1 })
      }
    }

    // Sort layers by their configured rank (not dagre's X position, which may
    // not respect the intended layer ordering)
    const layerAvgs = [...layerXSums.entries()]
      .map(([rank, { sum, count }]) => ({ rank, avgX: sum / count }))
      .sort((a, b) => a.rank - b.rank)

    // Compute spacing per layer based on how many intra-layer sub-ranks exist,
    // so layers with deep internal chains get more room.
    const allNodeIds = new Set(layoutNodes.map(n => n.id))
    const layerMaxSubRank = new Map<number, number>()

    for (const layerRank of distinctLayers) {
      const groupIds = new Set(layoutNodes.filter(n => n.data.layer === layerRank).map(n => n.id))
      const intraEdges = edges.filter(e => groupIds.has(e.source) && groupIds.has(e.target) && allNodeIds.has(e.source) && allNodeIds.has(e.target))

      if (intraEdges.length === 0) {
        layerMaxSubRank.set(layerRank!, 0)
        continue
      }

      // Quick topological depth calculation
      const inDeg = new Map<string, number>()
      const kids = new Map<string, string[]>()
      for (const id of groupIds) { inDeg.set(id, 0); kids.set(id, []) }
      for (const e of intraEdges) {
        inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1)
        kids.get(e.source)?.push(e.target)
      }
      const depth = new Map<string, number>()
      const queue = [...groupIds].filter(id => (inDeg.get(id) ?? 0) === 0)
      for (const id of queue) depth.set(id, 0)
      let maxDepth = 0
      while (queue.length > 0) {
        const cur = queue.shift()!
        const d = depth.get(cur) ?? 0
        for (const child of (kids.get(cur) ?? [])) {
          const nd = Math.max(depth.get(child) ?? 0, d + 1)
          depth.set(child, nd)
          maxDepth = Math.max(maxDepth, nd)
          const newDeg = (inDeg.get(child) ?? 1) - 1
          inDeg.set(child, newDeg)
          if (newDeg === 0) queue.push(child)
        }
      }
      layerMaxSubRank.set(layerRank!, maxDepth)
    }

    // Each sub-rank needs NODE_WIDTH + gap of space
    const SUB_RANK_OFFSET = NODE_WIDTH + 40
    const LAYER_GAP = 80 // gap between layers

    // Assign cumulative X positions accounting for each layer's internal width
    const layerTargetX = new Map<number, number>()
    let cumulativeX = 0
    for (const la of layerAvgs) {
      layerTargetX.set(la.rank, cumulativeX)
      const subRanks = layerMaxSubRank.get(la.rank) ?? 0
      const layerWidth = NODE_WIDTH + subRanks * SUB_RANK_OFFSET
      cumulativeX += layerWidth + LAYER_GAP
    }

    // Snap each node to its layer's target X
    for (const ln of layoutNodes) {
      const layer = ln.data.layer
      if (layer == null) continue
      const targetX = layerTargetX.get(layer)
      if (targetX != null) {
        ln.x = targetX
      }
    }

    // Intra-layer sub-ranking: within each layer, detect edges between nodes
    // in the same layer and offset children rightward so dependencies are visible.
    const layerGroups = new Map<number, LayoutItem[]>()
    for (const ln of layoutNodes) {
      const layer = ln.data.layer
      if (layer == null) continue
      const group = layerGroups.get(layer)
      if (group) group.push(ln)
      else layerGroups.set(layer, [ln])
    }

    for (const [, group] of layerGroups) {
      const nodeIds = new Set(group.map(n => n.id))
      const intraEdges = edges.filter(
        e => nodeIds.has(e.source) && nodeIds.has(e.target) && allNodeIds.has(e.source) && allNodeIds.has(e.target)
      )
      if (intraEdges.length === 0) continue

      const inDegree = new Map<string, number>()
      const children = new Map<string, string[]>()
      for (const id of nodeIds) { inDegree.set(id, 0); children.set(id, []) }
      for (const e of intraEdges) {
        inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
        children.get(e.source)?.push(e.target)
      }

      const subRank = new Map<string, number>()
      const queue = [...nodeIds].filter(id => (inDegree.get(id) ?? 0) === 0)
      for (const id of queue) subRank.set(id, 0)
      while (queue.length > 0) {
        const current = queue.shift()!
        const currentRank = subRank.get(current) ?? 0
        for (const child of (children.get(current) ?? [])) {
          const newRank = Math.max(subRank.get(child) ?? 0, currentRank + 1)
          subRank.set(child, newRank)
          const newDeg = (inDegree.get(child) ?? 1) - 1
          inDegree.set(child, newDeg)
          if (newDeg === 0) queue.push(child)
        }
      }
      for (const id of nodeIds) {
        if (!subRank.has(id)) subRank.set(id, 0)
      }

      // Apply X offset based on sub-rank
      for (const ln of group) {
        ln.x += (subRank.get(ln.id) ?? 0) * SUB_RANK_OFFSET
      }

      // Re-sort Y positions within each sub-rank so children are near their parents
      const bySubRank = new Map<number, LayoutItem[]>()
      for (const ln of group) {
        const sr = subRank.get(ln.id) ?? 0
        const arr = bySubRank.get(sr)
        if (arr) arr.push(ln)
        else bySubRank.set(sr, [ln])
      }

      const parents = new Map<string, string[]>()
      for (const e of intraEdges) {
        const arr = parents.get(e.target)
        if (arr) arr.push(e.source)
        else parents.set(e.target, [e.source])
      }

      const nodeY = new Map<string, number>()
      for (const ln of group) nodeY.set(ln.id, ln.y)

      for (const [sr, items] of bySubRank) {
        if (sr === 0) continue
        items.sort((a, b) => {
          const aP = parents.get(a.id) ?? []
          const bP = parents.get(b.id) ?? []
          const aAvgY = aP.length > 0 ? aP.reduce((s, p) => s + (nodeY.get(p) ?? 0), 0) / aP.length : a.y
          const bAvgY = bP.length > 0 ? bP.reduce((s, p) => s + (nodeY.get(p) ?? 0), 0) / bP.length : b.y
          return aAvgY - bAvgY
        })
        const currentYs = items.map(ln => ln.y).sort((a, b) => a - b)
        for (let i = 0; i < items.length; i++) items[i].y = currentYs[i]
      }
    }
  }

  const layoutEdges = edges.filter(
    (e) => g.hasNode(e.source) && g.hasNode(e.target)
  )

  return { nodes: layoutNodes, edges: layoutEdges }
}

export interface LineageFlowProps {
  nodes: LineageNode[]
  edges: LineageEdge[]
  pinnedIds?: Set<string>
  onTogglePin?: (id: string) => void
  onNodeClick?: (id: string) => void
  /** Map of folder node id → { modelCount, sourceCount } for folder rendering */
  folderData?: Record<string, { modelCount: number; sourceCount: number }>
  /** Set of currently expanded folder ids */
  expandedFolders?: Set<string>
  /** Called when a folder node is clicked */
  onFolderClick?: (folderId: string) => void
  /** Layer definitions for rendering vertical band backgrounds */
  layerConfig?: LayerDefinition[]
  /** Called when user double-clicks to navigate away (e.g. to exit fullscreen) */
  onNavigateAway?: () => void
  /** Column-level lineage data for column highlighting */
  columnLineageData?: ColumnLineageData
  /** Map of model ID → list of column names (for DagNode expansion) */
  modelColumns?: Record<string, string[]>
}

function LineageFlowInner({
  nodes,
  edges,
  pinnedIds,
  onTogglePin: _onTogglePin,
  onNodeClick,
  folderData,
  expandedFolders,
  onFolderClick,
  layerConfig,
  onNavigateAway,
  columnLineageData,
  modelColumns,
}: LineageFlowProps) {
  const navigate = useNavigate()
  const { fitView, getNodes } = useReactFlow()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // Column highlight state
  const selectedColumn = useColumnHighlightStore(s => s.selectedColumn)
  const expandedNodeIds = useColumnHighlightStore(s => s.expandedNodeIds)
  const autoExpandedNodeIds = useColumnHighlightStore(s => s.autoExpandedNodeIds)
  const manuallyCollapsedIds = useColumnHighlightStore(s => s.manuallyCollapsedIds)
  const clearColumnSelection = useColumnHighlightStore(s => s.clearSelection)

  // Combined set of all effectively expanded nodes (manual + auto - collapsed)
  const effectiveExpandedIds = useMemo(() => {
    const set = new Set(expandedNodeIds)
    for (const id of autoExpandedNodeIds) {
      if (!manuallyCollapsedIds.has(id)) set.add(id)
    }
    return set
  }, [expandedNodeIds, autoExpandedNodeIds, manuallyCollapsedIds])

  // Memoize reverse index for downstream column tracing
  const reverseIndex = useMemo(
    () => columnLineageData ? buildReverseIndex(columnLineageData) : new Map(),
    [columnLineageData],
  )

  // Compute column trace when a column is selected
  const columnTrace = useMemo(() => {
    if (!selectedColumn || !columnLineageData) return null
    return getColumnTraceResult(
      selectedColumn.modelId,
      selectedColumn.columnName,
      columnLineageData,
      reverseIndex,
    )
  }, [selectedColumn, columnLineageData, reverseIndex])
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isDraggingRef = useRef(false)
  const [dragOverrides, setDragOverrides] = useState<Record<string, { x: number; y: number }>>({})

  // Hover highlighting disabled — caused flicker when rapidly moving across nodes.

  const centerOnPinned = useCallback(() => {
    if (!pinnedIds || pinnedIds.size === 0) return
    const targets = getNodes().filter(n => pinnedIds.has(n.id))
    if (targets.length === 0) return
    fitView({ nodes: targets, duration: 300, padding: 0.3 })
  }, [pinnedIds, fitView, getNodes])

  const folderNodeIds = useMemo(
    () => new Set(Object.keys(folderData ?? {})),
    [folderData],
  )

  // Auto-expand column lists when the graph has few enough models.
  // Computed from raw nodes prop (before layout) to avoid circular dependency.
  const AUTO_EXPAND_THRESHOLD = 12
  const autoExpandNodeIds = useMemo(() => {
    if (!columnLineageData) return new Set<string>()

    const dataNodes = nodes.filter(n => !folderNodeIds.has(n.id))
    if (dataNodes.length > AUTO_EXPAND_THRESHOLD) return new Set<string>()

    const ids = new Set<string>()
    for (const n of dataNodes) {
      if (columnLineageData[n.id] != null) {
        ids.add(n.id)
      }
    }
    return ids
  }, [nodes, folderNodeIds, columnLineageData])

  // Combined set of effectively expanded nodes for layout calculation
  const layoutExpandedIds = useMemo(() => {
    const set = new Set(expandedNodeIds)
    for (const id of autoExpandNodeIds) {
      if (!manuallyCollapsedIds.has(id)) set.add(id)
    }
    return set
  }, [expandedNodeIds, autoExpandNodeIds, manuallyCollapsedIds])

  const layout = useMemo(
    () => computeLayout(nodes, edges, folderNodeIds, layoutExpandedIds, modelColumns),
    [nodes, edges, folderNodeIds, layoutExpandedIds, modelColumns],
  )

  // Highlighting — depth-capped chain for all pinned nodes
  const pinnedArray = useMemo(() => Array.from(pinnedIds ?? []), [pinnedIds])

  const highlightedSet = useMemo(() => {
    if (pinnedArray.length === 0) return null
    return getUnionChain(pinnedArray, edges, HIGHLIGHT_DEPTH_CAP)
  }, [pinnedArray, edges])

  // Compute layer bands from layout positions
  const layerBands = useMemo(() => {
    if (!layerConfig || layerConfig.length === 0) return []

    // Group layout nodes by their layer rank
    const rankBounds = new Map<number, { minX: number; maxX: number; minY: number; maxY: number }>()
    for (const ln of layout.nodes) {
      const layer = ln.data.layer
      if (layer == null) continue
      const bounds = rankBounds.get(layer)
      if (bounds) {
        bounds.minX = Math.min(bounds.minX, ln.x)
        bounds.maxX = Math.max(bounds.maxX, ln.x + ln.width)
        bounds.minY = Math.min(bounds.minY, ln.y)
        bounds.maxY = Math.max(bounds.maxY, ln.y + ln.height)
      } else {
        rankBounds.set(layer, {
          minX: ln.x,
          maxX: ln.x + ln.width,
          minY: ln.y,
          maxY: ln.y + ln.height,
        })
      }
    }

    // Global Y bounds for full-height bands
    let globalMinY = Infinity
    let globalMaxY = -Infinity
    for (const b of rankBounds.values()) {
      globalMinY = Math.min(globalMinY, b.minY)
      globalMaxY = Math.max(globalMaxY, b.maxY)
    }

    const BAND_PADDING = 30
    return layerConfig
      .filter(l => rankBounds.has(l.rank))
      .map(l => {
        const b = rankBounds.get(l.rank)!
        return {
          name: l.name,
          color: l.color,
          x: b.minX - BAND_PADDING,
          y: globalMinY - BAND_PADDING * 2,
          width: b.maxX - b.minX + BAND_PADDING * 2,
          height: globalMaxY - globalMinY + BAND_PADDING * 4,
        }
      })
  }, [layout.nodes, layerConfig])

  // Build React Flow nodes
  const rfNodes = useMemo((): Node[] => {
    // Add layer band background nodes first (lowest z-index)
    const bandNodes: Node[] = layerBands.map((band) => ({
      id: `__layer_band_${band.name}`,
      type: 'layerBand',
      position: { x: band.x, y: band.y },
      data: {
        label: band.name,
        color: band.color,
        width: band.width,
        height: band.height,
      },
      selectable: false,
      draggable: false,
      connectable: false,
      style: { zIndex: -10, pointerEvents: 'none' as const },
    }))

    const dataNodes: Node[] = layout.nodes.map((ln) => {
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
            opacity: 1, // Updated in applyHighlightPass below
            transition: 'none',
          },
        }
      }

      const nodeColumns = modelColumns?.[ln.id]
      const hasColumnLineage = columnLineageData != null && columnLineageData[ln.id] != null
      const nodeHighlightedCols = columnTrace?.highlightedColumns.get(ln.id)
      const inColumnTrace = nodeHighlightedCols != null && nodeHighlightedCols.size > 0

      // When column trace is active, dim nodes not involved
      const dimmedByColumnTrace = columnTrace != null && !inColumnTrace

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
          isActive: false, // Updated in applyHighlightPass below
          folder: ln.data.folder,
          schema: ln.data.schema,
          columns: nodeColumns,
          hasColumnLineage,
          autoExpanded: autoExpandNodeIds.has(ln.id),
          highlightedColumns: nodeHighlightedCols,
          inColumnTrace: inColumnTrace && !effectiveExpandedIds.has(ln.id),
          noColumnData: false, // Updated in applyHighlightPass below
        },
        style: {
          opacity: dimmedByColumnTrace ? 0.3 : 1,
          transition: 'none',
        },
      }
    })

    return [...bandNodes, ...dataNodes]
  }, [layout.nodes, folderData, expandedFolders, layerBands, modelColumns, columnLineageData, columnTrace, effectiveExpandedIds, autoExpandNodeIds])

  // Reset drag overrides when the layout recomputes (depth/filter changes)
  const layoutRef = useRef(layout)
  useEffect(() => {
    if (layoutRef.current !== layout) {
      layoutRef.current = layout
      setDragOverrides({})
    }
  }, [layout])

  // Lightweight pass: apply highlight opacity + isActive + drag overrides
  // This recomputes on hover but only patches style/data fields — rfNodes
  // itself is NOT recreated, so DagNode memo sees stable data references
  // for nodes whose highlight state hasn't changed.
  const displayNodes = useMemo((): Node[] => {
    const hasDragOverrides = Object.keys(dragOverrides).length > 0

    return rfNodes.map(node => {
      const override = hasDragOverrides ? dragOverrides[node.id] : undefined
      const isBand = node.id.startsWith('__layer_band_')

      if (isBand) {
        return override ? { ...node, position: { x: override.x, y: override.y } } : node
      }

      const isFolder = node.type === 'folder'
      const highlighted = !highlightedSet || highlightedSet.has(node.id)
      const isPinnedNode = pinnedIds?.has(node.id) ?? false

      // Only create new objects if something actually changed
      const currentOpacity = (node.style as Record<string, unknown>)?.opacity
      const targetOpacity = highlighted ? (currentOpacity === 0.3 ? 0.3 : 1) : 0.4
      const currentIsActive = (node.data as Record<string, unknown>)?.isActive
      const currentNoColumnData = (node.data as Record<string, unknown>)?.noColumnData
      const targetNoColumnData = !isFolder && columnTrace != null
        && !(columnLineageData != null && columnLineageData[node.id] != null)
        && highlightedSet?.has(node.id)

      const styleChanged = currentOpacity !== targetOpacity
      const dataChanged = currentIsActive !== isPinnedNode || currentNoColumnData !== targetNoColumnData

      if (!styleChanged && !dataChanged && !override) return node

      return {
        ...node,
        ...(override ? { position: { x: override.x, y: override.y } } : {}),
        ...(dataChanged ? {
          data: { ...node.data, isActive: isPinnedNode, noColumnData: targetNoColumnData },
        } : {}),
        ...(styleChanged ? {
          style: { ...node.style, opacity: targetOpacity },
        } : {}),
      }
    })
  }, [rfNodes, dragOverrides, highlightedSet, pinnedIds, columnTrace, columnLineageData])

  // Handle node drag changes
  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    // Only process position changes from dragging
    const positionChanges = changes.filter(
      (c): c is NodeChange & { type: 'position'; id: string; position?: { x: number; y: number } } =>
        c.type === 'position' && 'position' in c && c.position != null
    )
    if (positionChanges.length === 0) return
    setDragOverrides(prev => {
      const next = { ...prev }
      for (const change of positionChanges) {
        next[change.id] = { x: change.position!.x, y: change.position!.y }
      }
      return next
    })
  }, [])

  // Shared marker definitions — avoids creating per-edge marker objects
  const MARKER_HIGHLIGHTED = useMemo(() => ({
    type: MarkerType.ArrowClosed as const,
    color: '#2563eb',
    width: 16,
    height: 12,
  }), [])

  const MARKER_DEFAULT = useMemo(() => ({
    type: MarkerType.ArrowClosed as const,
    color: '#94a3b8',
    width: 16,
    height: 12,
  }), [])

  const MARKER_COLUMN = useMemo(() => ({
    type: MarkerType.ArrowClosed as const,
    color: '#f59e0b',
    width: 14,
    height: 10,
  }), [])

  // Build React Flow edges — base structure without highlight styling
  const rfEdgesBase = useMemo((): Edge[] => {
    const modelEdges: Edge[] = layout.edges.map((e) => ({
      id: `${e.source}__${e.target}`,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      animated: false,
      style: {
        stroke: 'var(--text-muted, #94a3b8)',
        strokeWidth: 1.5,
        opacity: 0.5,
      },
      markerEnd: MARKER_DEFAULT,
    }))

    // Column-level edges
    if (!columnTrace) return modelEdges

    const COLUMN_EDGE_COLORS: Record<string, string> = {
      direct: '#16a34a',
      derived: '#f59e0b',
      aggregated: '#7c3aed',
    }

    const columnEdges: Edge[] = columnTrace.edges.map((ce) => {
      const sourceExpanded = effectiveExpandedIds.has(ce.sourceModel)
      const targetExpanded = effectiveExpandedIds.has(ce.targetModel)
      const edgeColor = COLUMN_EDGE_COLORS[ce.transformation] ?? '#f59e0b'

      return {
        id: `col__${ce.sourceModel}__${ce.sourceColumn}__${ce.targetModel}__${ce.targetColumn}`,
        source: ce.sourceModel,
        target: ce.targetModel,
        sourceHandle: sourceExpanded ? `col-${ce.sourceColumn}-source` : undefined,
        targetHandle: targetExpanded ? `col-${ce.targetColumn}-target` : undefined,
        type: 'smoothstep',
        animated: false,
        label: ce.transformation,
        labelStyle: {
          fontSize: 9,
          fontWeight: 600,
          fill: edgeColor,
          letterSpacing: '0.02em',
        },
        labelBgStyle: {
          fill: 'var(--bg, #fff)',
          fillOpacity: 0.85,
          rx: 3,
          ry: 3,
        },
        labelBgPadding: [4, 2] as [number, number],
        style: {
          stroke: edgeColor,
          strokeWidth: 2,
          strokeDasharray: '6 3',
          opacity: 0.9,
        },
        markerEnd: MARKER_COLUMN,
        zIndex: 10,
      }
    })

    return [...modelEdges, ...columnEdges]
  }, [layout.edges, MARKER_DEFAULT, MARKER_COLUMN, columnTrace, effectiveExpandedIds])

  // Lightweight pass: apply highlight styling to edges without recreating the base array
  const rfEdges = useMemo((): Edge[] => {
    if (!highlightedSet && !columnTrace) return rfEdgesBase

    const isColumnTraceActive = columnTrace != null

    return rfEdgesBase.map(edge => {
      // Skip column edges — they're already styled
      if (edge.id.startsWith('col__')) return edge

      const isHighlighted = highlightedSet
        ? highlightedSet.has(edge.source) && highlightedSet.has(edge.target)
        : false

      return {
        ...edge,
        style: {
          stroke: isHighlighted ? '#2563eb' : 'var(--text-muted, #94a3b8)',
          strokeWidth: isHighlighted ? 2 : 1.5,
          opacity: isColumnTraceActive ? 0.08 : !highlightedSet ? 0.5 : isHighlighted ? 0.8 : 0.15,
        },
        markerEnd: isHighlighted ? MARKER_HIGHLIGHTED : MARKER_DEFAULT,
      }
    })
  }, [rfEdgesBase, highlightedSet, columnTrace, MARKER_HIGHLIGHTED, MARKER_DEFAULT])

  // Fit view when data changes
  useEffect(() => {
    if (layout.nodes.length > 0) {
      requestAnimationFrame(() => fitView({ padding: 0.1 }))
    }
  }, [layout.nodes.length, layout.edges.length, fitView])

  const handleNodeDragStart = useCallback(() => {
    isDraggingRef.current = true
  }, [])

  const handleNodeDragStop = useCallback(() => {
    isDraggingRef.current = false
  }, [])

  // Single click → open side panel; double click → navigate to detail page
  // Cmd/Ctrl+Click → toggle pin
  const handleNodeClick: NodeMouseHandler = useCallback((event, node) => {
    if (node.id.startsWith('folder:') && onFolderClick) {
      onFolderClick(node.id)
      return
    }
    if (node.id.startsWith('__layer_band_')) return

    // Cmd+Click / Ctrl+Click toggles the pin state
    if ((event.metaKey || event.ctrlKey) && _onTogglePin) {
      event.preventDefault()
      _onTogglePin(node.id)
      return
    }

    // Use a timer to distinguish single vs double click
    if (clickTimerRef.current) {
      // Double click detected — clear the single-click timer
      clearTimeout(clickTimerRef.current)
      clickTimerRef.current = null

      // Navigate to detail page
      onNavigateAway?.()
      const type = node.id.startsWith('source.') ? 'source' : 'model'
      navigate(`/${type}/${encodeURIComponent(node.id)}`)
    } else {
      // Start single-click timer
      clickTimerRef.current = setTimeout(() => {
        clickTimerRef.current = null
        // Single click: open side panel
        setSelectedNodeId(prev => prev === node.id ? null : node.id)
        if (onNodeClick) onNodeClick(node.id)
      }, 250)
    }
  }, [navigate, onNodeClick, onFolderClick, onNavigateAway, _onTogglePin])

  // Close panel when clicking canvas background
  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null)
    clearColumnSelection()
  }, [clearColumnSelection])

  // Lookup for selected node detail panel
  const selectedNodeData = useMemo(() => {
    if (!selectedNodeId) return null
    return nodes.find(n => n.id === selectedNodeId) ?? null
  }, [selectedNodeId, nodes])

  if (nodes.length === 0) {
    return <div className="text-[var(--text-muted)] text-sm">No lineage data available.</div>
  }

  return (
    <ReactFlow
      nodes={displayNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      onNodesChange={handleNodesChange}
      onNodeDragStart={handleNodeDragStart}
      onNodeDragStop={handleNodeDragStop}
      onNodeClick={handleNodeClick}
      onPaneClick={handlePaneClick}
      nodesDraggable={true}
      nodesConnectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      edgesReconnectable={false}
      elementsSelectable={false}
      selectNodesOnDrag={false}
      autoPanOnNodeDrag={false}
      fitView
      minZoom={0.05}
      maxZoom={3}
    >
      <Controls showInteractive={false}>
        {pinnedIds && pinnedIds.size > 0 && (
          <button
            onClick={centerOnPinned}
            title={pinnedIds.size === 1 ? 'Center on pinned model' : `Fit all ${pinnedIds.size} pinned models`}
            className="react-flow__controls-button"
            style={{ color: '#f59e0b' }}
          >
            <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <circle cx={12} cy={12} r={3} />
              <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
            </svg>
          </button>
        )}
      </Controls>
      <MiniMap
        nodeColor={(node) => {
          if (node.id.startsWith('folder:')) return '#64748b'
          return RESOURCE_COLORS[(node.data as Record<string, unknown>)?.resource_type as string] ?? '#6b7280'
        }}
        maskColor="rgba(0,0,0,0.25)"
        pannable
        zoomable
      />
      {/* Node detail side panel */}
      {selectedNodeData && (
        <div
          className="react-flow__panel"
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: 280,
            height: '100%',
            background: 'var(--bg, #fff)',
            borderLeft: '1px solid var(--border, #e2e8f0)',
            zIndex: 10,
            overflow: 'auto',
            padding: 16,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text, #0f172a)', wordBreak: 'break-word', lineHeight: 1.3 }}>
              {selectedNodeData.name}
            </div>
            <button
              onClick={() => setSelectedNodeId(null)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                color: 'var(--text-muted, #64748b)', flexShrink: 0, marginLeft: 8,
              }}
            >
              <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
            <PanelRow label="Type" value={selectedNodeData.resource_type} />
            {selectedNodeData.materialization && <PanelRow label="Materialization" value={selectedNodeData.materialization} />}
            {selectedNodeData.schema && <PanelRow label="Schema" value={selectedNodeData.schema} />}
            {selectedNodeData.folder && <PanelRow label="Folder" value={selectedNodeData.folder} />}
            <PanelRow label="Has description" value={selectedNodeData.has_description ? 'Yes' : 'No'} />
            {selectedNodeData.test_status !== 'none' && (
              <PanelRow label="Test status" value={selectedNodeData.test_status} />
            )}
            {selectedNodeData.tags.length > 0 && (
              <div>
                <div style={{ color: 'var(--text-muted, #64748b)', marginBottom: 2 }}>Tags</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {selectedNodeData.tags.map(t => (
                    <span key={t} style={{
                      padding: '1px 6px', borderRadius: 4, fontSize: 11,
                      background: 'var(--bg-surface, #f1f5f9)', color: 'var(--text, #0f172a)',
                    }}>{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
          <button
            onClick={() => {
              onNavigateAway?.()
              const type = selectedNodeData.resource_type === 'source' ? 'source' : 'model'
              navigate(`/${type}/${encodeURIComponent(selectedNodeData.id)}`)
            }}
            style={{
              marginTop: 16, width: '100%', padding: '6px 0', fontSize: 12, fontWeight: 600,
              border: '1px solid var(--border, #e2e8f0)', borderRadius: 6,
              background: 'var(--bg-surface, #f1f5f9)', color: 'var(--text, #0f172a)',
              cursor: 'pointer',
            }}
          >
            View details →
          </button>
        </div>
      )}
    </ReactFlow>
  )
}

function PanelRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
      <span style={{ color: 'var(--text-muted, #64748b)' }}>{label}</span>
      <span style={{ color: 'var(--text, #0f172a)', fontWeight: 500, textAlign: 'right', wordBreak: 'break-word' }}>{value}</span>
    </div>
  )
}

export function LineageFlow(props: LineageFlowProps) {
  return (
    <ReactFlowProvider>
      <LineageFlowInner {...props} />
    </ReactFlowProvider>
  )
}
