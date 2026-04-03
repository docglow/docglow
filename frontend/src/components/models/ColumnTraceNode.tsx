import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { TraceNodeData } from '../../utils/columnTraceLayout'

const RESOURCE_COLORS: Record<string, string> = {
  model: '#2563eb',
  source: '#16a34a',
  seed: '#6b7280',
  snapshot: '#7c3aed',
  exposure: '#d97706',
  metric: '#7c3aed',
}

const AMBER = '#f59e0b'
const COLUMN_ROW_HEIGHT = 22

function ColumnTraceNodeComponent({ data }: NodeProps) {
  const { modelName, resourceType, columns, isCurrent, currentColumn } =
    data as unknown as TraceNodeData

  const fill = RESOURCE_COLORS[resourceType] ?? '#6b7280'

  return (
    <>
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
      <div
        style={{
          width: 180,
          borderRadius: 6,
          border: isCurrent ? `2.5px solid ${AMBER}` : '1px solid var(--border, #e2e8f0)',
          boxShadow: isCurrent
            ? `0 0 0 3px ${AMBER}33, 0 0 12px ${AMBER}44`
            : '0 1px 3px rgba(0,0,0,0.08)',
          background: 'var(--bg, #fff)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'stretch', height: 36 }}>
          <div style={{ width: 4, background: fill, flexShrink: 0 }} />
          <div
            style={{
              padding: '4px 8px',
              overflow: 'hidden',
              minWidth: 0,
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--text, #0f172a)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {modelName}
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-muted, #64748b)' }}>
              {resourceType}
            </div>
          </div>
        </div>

        {/* Column list */}
        <div
          style={{
            borderTop: '1px solid var(--border, #e2e8f0)',
            maxHeight: 200,
            overflowY: 'auto',
          }}
        >
          {columns.map((col) => {
            const isCurrentCol = currentColumn === col
            return (
              <div
                key={col}
                style={{
                  height: COLUMN_ROW_HEIGHT,
                  padding: '0 8px 0 12px',
                  fontSize: 10,
                  fontWeight: isCurrentCol ? 700 : 400,
                  color: isCurrentCol ? AMBER : 'var(--text, #0f172a)',
                  background: isCurrentCol ? `${AMBER}20` : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  position: 'relative',
                }}
                title={col}
              >
                {col}
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
      </div>
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
    </>
  )
}

export const ColumnTraceNode = memo(ColumnTraceNodeComponent)
