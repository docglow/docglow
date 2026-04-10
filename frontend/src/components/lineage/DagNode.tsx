import { memo, useCallback } from 'react'
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
const MAX_VISIBLE_COLUMNS = 20
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
  autoExpanded?: boolean
  /** Map of column names that should be highlighted in the column trace */
  highlightedColumns?: Set<string>
  /** Whether this node participates in a column trace (for amber border on collapsed nodes) */
  inColumnTrace?: boolean
  /** Node is in the lineage chain but has no column lineage data */
  noColumnData?: boolean
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
    noColumnData,
  } = data as DagNodeData

  const { autoExpanded } = data as DagNodeData
  const isManuallyExpanded = useColumnHighlightStore(s => s.expandedNodeIds.has(id))
  const isManuallyCollapsed = useColumnHighlightStore(s => s.manuallyCollapsedIds.has(id))
  const isExpanded = isManuallyExpanded || (!!autoExpanded && !isManuallyCollapsed)
  const isThisSelected = useColumnHighlightStore(
    s => s.selectedColumn?.modelId === id
  )
  const selectedColumnName = useColumnHighlightStore(
    s => s.selectedColumn?.modelId === id ? s.selectedColumn.columnName : null
  )
  const toggleNodeExpanded = useColumnHighlightStore(s => s.toggleNodeExpanded)
  const selectColumn = useColumnHighlightStore(s => s.selectColumn)

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
    : noColumnData
      ? `2px dashed ${AMBER}88`
      : borderColor !== 'transparent'
        ? `2px solid ${borderColor}`
        : '1px solid var(--border, #e2e8f0)'

  const boxShadow = showAmberBorder
    ? `0 0 0 3px ${AMBER}33, 0 0 12px ${AMBER}44`
    : noColumnData
      ? `0 0 0 2px ${AMBER}22`
      : undefined

  const tooltipText = [schema && `Schema: ${schema}`, folder && `Folder: ${folder}`].filter(Boolean).join('\n')
  const canExpand = hasColumnLineage && columns && columns.length > 0

  // All columns are rendered inside a scroll container capped at MAX_VISIBLE_COLUMNS height
  const allColumns = columns ?? []

  return (
    <>
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
      <div
        className="dag-node-container"
        title={tooltipText || undefined}
        style={{
          width: 180,
          borderRadius: 6,
          border,
          boxShadow,
          background: showAmberBorder ? 'var(--bg, #fff)' : 'var(--bg, #fff)',
          overflow: 'visible',
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
            className="dag-node-columns"
            style={{
              borderTop: '1px solid var(--border, #e2e8f0)',
              border: '1px solid var(--border, #e2e8f0)',
              borderRadius: '0 0 6px 6px',
              maxHeight: MAX_VISIBLE_COLUMNS * COLUMN_ROW_HEIGHT + 4,
              overflowY: 'auto',
              overflowX: 'hidden',
              background: 'var(--bg, #fff)',
              position: 'relative',
              zIndex: 20,
              boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
            }}
          >
            {allColumns.map((col) => {
              const isSelected = isThisSelected && selectedColumnName === col
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
          </div>
        )}

        {/* Tooltip via native title — no React state, no re-renders */}
      </div>
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
    </>
  )
}

export const DagNode = memo(DagNodeComponent)
