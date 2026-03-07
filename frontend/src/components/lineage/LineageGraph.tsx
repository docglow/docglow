import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { LineageNode, LineageEdge } from '../../types'
import { useLineageLayout, type LayoutNode } from '../../hooks/useLineage'
import { getFullChain } from '../../utils/graphTraversal'

interface LineageGraphProps {
  nodes: LineageNode[]
  edges: LineageEdge[]
  highlightId?: string
  onNodeClick?: (id: string) => void
}

const RESOURCE_COLORS: Record<string, string> = {
  model: '#2563eb',
  source: '#16a34a',
  seed: '#6b7280',
  snapshot: '#7c3aed',
  exposure: '#d97706',
  metric: '#7c3aed',
}

const TEST_STATUS_BORDER: Record<string, string> = {
  pass: '#16a34a',
  fail: '#dc2626',
  warn: '#d97706',
  none: 'transparent',
}

function EdgePath({ points, highlighted }: { points: { x: number; y: number }[]; highlighted: boolean }) {
  if (points.length < 2) return null

  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`)
    .join(' ')

  return (
    <path
      d={d}
      fill="none"
      stroke={highlighted ? '#2563eb' : 'var(--text-muted, #94a3b8)'}
      strokeWidth={highlighted ? 2 : 1.5}
      strokeOpacity={highlighted ? 0.8 : 0.3}
      markerEnd="url(#arrowhead)"
    />
  )
}

function DagNode({
  node,
  isHighlighted,
  isActive,
  onMouseEnter,
  onMouseLeave,
  onClick,
}: {
  node: LayoutNode
  isHighlighted: boolean
  isActive: boolean
  onMouseEnter: () => void
  onMouseLeave: () => void
  onClick: () => void
}) {
  const fill = RESOURCE_COLORS[node.resource_type] ?? '#6b7280'
  const borderColor = TEST_STATUS_BORDER[node.test_status] ?? 'transparent'
  const opacity = isHighlighted ? 1 : 0.4

  return (
    <g
      transform={`translate(${node.x}, ${node.y})`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      style={{ cursor: 'pointer', opacity }}
    >
      <rect
        width={node.width}
        height={node.height}
        rx={6}
        ry={6}
        fill="var(--bg, #fff)"
        stroke={isActive ? fill : borderColor !== 'transparent' ? borderColor : 'var(--border, #e2e8f0)'}
        strokeWidth={isActive ? 2.5 : borderColor !== 'transparent' ? 2 : 1}
      />
      {/* Resource type indicator */}
      <rect
        x={0}
        y={0}
        width={4}
        height={node.height}
        rx={2}
        fill={fill}
      />
      <text
        x={14}
        y={18}
        fontSize={12}
        fontWeight={600}
        fill="var(--text, #0f172a)"
        className="select-none"
      >
        {node.name.length > 20 ? `${node.name.slice(0, 18)}...` : node.name}
      </text>
      <text
        x={14}
        y={34}
        fontSize={10}
        fill="var(--text-muted, #64748b)"
        className="select-none"
      >
        {node.resource_type}{node.materialization ? ` · ${node.materialization}` : ''}
      </text>
    </g>
  )
}

export function LineageGraph({ nodes, edges, highlightId, onNodeClick }: LineageGraphProps) {
  const layout = useLineageLayout(nodes, edges)
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [isPanning, setIsPanning] = useState(false)
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 })

  // Build full-chain highlighting (upstream + downstream)
  const activeId = hoveredId ?? highlightId ?? null
  const highlighted = useMemo(() => {
    if (!activeId) return new Set(nodes.map(n => n.id))
    return getFullChain(activeId, edges)
  }, [activeId, nodes, edges])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setZoom(z => Math.max(0.2, Math.min(3, z * delta)))
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    setIsPanning(true)
    panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y }
  }, [pan])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return
    setPan({
      x: panStart.current.panX + (e.clientX - panStart.current.x),
      y: panStart.current.panY + (e.clientY - panStart.current.y),
    })
  }, [isPanning])

  const handleMouseUp = useCallback(() => {
    setIsPanning(false)
  }, [])

  // Center on first render
  useEffect(() => {
    if (containerRef.current && layout.width > 0) {
      const rect = containerRef.current.getBoundingClientRect()
      const scaleX = rect.width / layout.width
      const scaleY = rect.height / layout.height
      const scale = Math.min(scaleX, scaleY, 1) * 0.9
      setZoom(scale)
      setPan({
        x: (rect.width - layout.width * scale) / 2,
        y: (rect.height - layout.height * scale) / 2,
      })
    }
  }, [layout.width, layout.height])

  const handleNodeClick = useCallback((id: string) => {
    if (onNodeClick) {
      onNodeClick(id)
      return
    }
    const type = id.startsWith('source.') ? 'source' : 'model'
    navigate(`/${type}/${encodeURIComponent(id)}`)
  }, [navigate, onNodeClick])

  if (layout.nodes.length === 0) {
    return <div className="text-[var(--text-muted)] text-sm">No lineage data available.</div>
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-full overflow-hidden border border-[var(--border)] rounded-lg bg-[var(--bg-surface)] select-none"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      style={{ cursor: isPanning ? 'grabbing' : 'grab' }}
    >
      <svg
        width="100%"
        height="100%"
        style={{ minHeight: '400px' }}
      >
        <defs>
          <marker
            id="arrowhead"
            markerWidth={8}
            markerHeight={6}
            refX={8}
            refY={3}
            orient="auto"
          >
            <polygon
              points="0 0, 8 3, 0 6"
              fill="var(--text-muted, #94a3b8)"
              fillOpacity={0.5}
            />
          </marker>
        </defs>
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {layout.edges.map((edge, i) => (
            <EdgePath
              key={i}
              points={edge.points}
              highlighted={!!activeId && highlighted.has(edge.source) && highlighted.has(edge.target)}
            />
          ))}
          {layout.nodes.map((node) => (
            <DagNode
              key={node.id}
              node={node}
              isHighlighted={highlighted.has(node.id)}
              isActive={node.id === (hoveredId ?? highlightId)}
              onMouseEnter={() => setHoveredId(node.id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => handleNodeClick(node.id)}
            />
          ))}
        </g>
      </svg>

      {/* Zoom controls */}
      <div className="absolute bottom-3 right-3 flex gap-1">
        <button
          onClick={() => setZoom(z => Math.min(3, z * 1.2))}
          className="w-8 h-8 rounded bg-[var(--bg)] border border-[var(--border)]
                     flex items-center justify-center text-sm hover:bg-[var(--bg-surface)]
                     cursor-pointer"
        >+</button>
        <button
          onClick={() => setZoom(z => Math.max(0.2, z * 0.8))}
          className="w-8 h-8 rounded bg-[var(--bg)] border border-[var(--border)]
                     flex items-center justify-center text-sm hover:bg-[var(--bg-surface)]
                     cursor-pointer"
        >−</button>
        <button
          onClick={() => {
            if (!containerRef.current) return
            const rect = containerRef.current.getBoundingClientRect()
            const scaleX = rect.width / layout.width
            const scaleY = rect.height / layout.height
            const scale = Math.min(scaleX, scaleY, 1) * 0.9
            setZoom(scale)
            setPan({
              x: (rect.width - layout.width * scale) / 2,
              y: (rect.height - layout.height * scale) / 2,
            })
          }}
          className="w-8 h-8 rounded bg-[var(--bg)] border border-[var(--border)]
                     flex items-center justify-center text-xs hover:bg-[var(--bg-surface)]
                     cursor-pointer"
          title="Fit to screen"
        >Fit</button>
      </div>
    </div>
  )
}
