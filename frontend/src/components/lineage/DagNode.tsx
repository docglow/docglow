import { memo, useState, useRef, useCallback } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useColumnHighlightStore } from '../../stores/columnHighlightStore'

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

const COLUMN_ROW_HEIGHT = 22
const MAX_VISIBLE_COLUMNS = 30
const AMBER = '#f59e0b'

export interface DagNodeData {
  name: string
  resource_type: string
  materialization: string
  test_status: string
  isActive: boolean
  folder?: string
  schema?: string
  columns?: string[]
  hasColumnLineage?: boolean
  /** Map of column names that should be highlighted in the column trace */
  highlightedColumns?: Set<string>
  /** Whether this node participates in a column trace (for amber border on collapsed nodes) */
  inColumnTrace?: boolean
  [key: string]: unknown
}

function DagNodeComponent({ data, id }: NodeProps) {
  const {
    name,
    resource_type,
    materialization,
    test_status,
    isActive,
    folder,
    schema,
    columns,
    hasColumnLineage,
    highlightedColumns,
    inColumnTrace,
  } = data as DagNodeData

  const [showTooltip, setShowTooltip] = useState(false)
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const expandedNodeIds = useColumnHighlightStore(s => s.expandedNodeIds)
  const selectedColumn = useColumnHighlightStore(s => s.selectedColumn)
  const toggleNodeExpanded = useColumnHighlightStore(s => s.toggleNodeExpanded)
  const selectColumn = useColumnHighlightStore(s => s.selectColumn)

  const isExpanded = expandedNodeIds.has(id)

  const handleMouseEnter = useCallback(() => {
    hoverTimer.current = setTimeout(() => setShowTooltip(true), 500)
  }, [])

  const handleMouseLeave = useCallback(() => {
    if (hoverTimer.current) {
      clearTimeout(hoverTimer.current)
      hoverTimer.current = null
    }
    setShowTooltip(false)
  }, [])

  const handleExpandClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    toggleNodeExpanded(id)
  }, [id, toggleNodeExpanded])

  const handleColumnClick = useCallback((e: React.MouseEvent, colName: string) => {
    e.stopPropagation()
    selectColumn(id, colName)
  }, [id, selectColumn])

  const fill = RESOURCE_COLORS[resource_type] ?? '#6b7280'
  const borderColor = TEST_STATUS_BORDER[test_status] ?? 'transparent'

  const showAmberBorder = isActive || inColumnTrace
  const border = showAmberBorder
    ? `2.5px solid ${AMBER}`
    : borderColor !== 'transparent'
      ? `2px solid ${borderColor}`
      : '1px solid var(--border, #e2e8f0)'

  const boxShadow = showAmberBorder
    ? `0 0 0 3px ${AMBER}33, 0 0 12px ${AMBER}44`
    : undefined

  const hasTooltipContent = folder || schema
  const canExpand = hasColumnLineage && columns && columns.length > 0

  const visibleColumns = columns
    ? columns.slice(0, MAX_VISIBLE_COLUMNS)
    : []
  const hasMore = columns ? columns.length > MAX_VISIBLE_COLUMNS : false

  return (
    <>
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
      <div
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          width: 180,
          borderRadius: 6,
          border,
          boxShadow,
          background: showAmberBorder ? '#fef3c710' : 'var(--bg, #fff)',
          overflow: 'hidden',
          cursor: 'pointer',
          position: 'relative',
        }}
      >
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'stretch', height: 44 }}>
          <div style={{ width: 4, background: fill, flexShrink: 0 }} />
          <div style={{ padding: '4px 8px', overflow: 'hidden', minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text, #0f172a)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {name}
            </div>
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-muted, #64748b)',
                whiteSpace: 'nowrap',
              }}
            >
              {resource_type}{materialization ? ` · ${materialization}` : ''}
            </div>
          </div>
          {/* Expand chevron */}
          {canExpand && (
            <button
              onClick={handleExpandClick}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '0 6px',
                color: 'var(--text-muted, #64748b)',
                display: 'flex',
                alignItems: 'center',
                flexShrink: 0,
              }}
              title={isExpanded ? 'Hide columns' : 'Show columns'}
            >
              <svg
                width={10}
                height={10}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2.5}
                style={{
                  transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.15s ease',
                }}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
          )}
        </div>

        {/* Expanded column list */}
        {isExpanded && columns && (
          <div
            style={{
              borderTop: '1px solid var(--border, #e2e8f0)',
              maxHeight: MAX_VISIBLE_COLUMNS * COLUMN_ROW_HEIGHT + 4,
              overflowY: 'auto',
              overflowX: 'hidden',
            }}
          >
            {visibleColumns.map((col) => {
              const isSelected = selectedColumn?.modelId === id && selectedColumn?.columnName === col
              const isHighlighted = highlightedColumns?.has(col)
              const colBg = isSelected
                ? `${AMBER}30`
                : isHighlighted
                  ? `${AMBER}15`
                  : 'transparent'

              return (
                <div
                  key={col}
                  onClick={(e) => handleColumnClick(e, col)}
                  style={{
                    height: COLUMN_ROW_HEIGHT,
                    padding: '0 8px 0 12px',
                    fontSize: 10,
                    color: isSelected || isHighlighted ? AMBER : 'var(--text, #0f172a)',
                    fontWeight: isSelected ? 600 : 400,
                    background: colBg,
                    display: 'flex',
                    alignItems: 'center',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    position: 'relative',
                    transition: 'background 0.1s ease',
                  }}
                  title={col}
                >
                  {col}
                  {/* Per-column handles for edge connections */}
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={`col-${col}-target`}
                    className="!opacity-0 !w-0 !h-0"
                    style={{ top: '50%' }}
                  />
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={`col-${col}-source`}
                    className="!opacity-0 !w-0 !h-0"
                    style={{ top: '50%' }}
                  />
                </div>
              )
            })}
            {hasMore && (
              <div
                style={{
                  height: COLUMN_ROW_HEIGHT,
                  padding: '0 8px 0 12px',
                  fontSize: 10,
                  color: 'var(--text-muted, #64748b)',
                  fontStyle: 'italic',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                +{columns.length - MAX_VISIBLE_COLUMNS} more columns
              </div>
            )}
          </div>
        )}

        {/* Hover tooltip */}
        {showTooltip && hasTooltipContent && !isExpanded && (
          <div
            style={{
              position: 'absolute',
              bottom: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginBottom: 6,
              background: 'var(--bg, #1e293b)',
              border: '1px solid var(--border, #334155)',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 11,
              color: 'var(--text, #e2e8f0)',
              whiteSpace: 'nowrap',
              zIndex: 50,
              pointerEvents: 'none',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {schema && (
              <div><span style={{ color: 'var(--text-muted, #94a3b8)' }}>Schema: </span>{schema}</div>
            )}
            {folder && (
              <div><span style={{ color: 'var(--text-muted, #94a3b8)' }}>Folder: </span>{folder}</div>
            )}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
    </>
  )
}

export const DagNode = memo(DagNodeComponent)
