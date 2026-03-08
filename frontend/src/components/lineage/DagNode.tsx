import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

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

export interface DagNodeData {
  name: string
  resource_type: string
  materialization: string
  test_status: string
  isActive: boolean
  [key: string]: unknown
}

function DagNodeComponent({ data }: NodeProps) {
  const {
    name,
    resource_type,
    materialization,
    test_status,
    isActive,
  } = data as DagNodeData

  const fill = RESOURCE_COLORS[resource_type] ?? '#6b7280'
  const borderColor = TEST_STATUS_BORDER[test_status] ?? 'transparent'

  const ACTIVE_COLOR = '#f59e0b' // amber-500

  const border = isActive
    ? `2.5px solid ${ACTIVE_COLOR}`
    : borderColor !== 'transparent'
      ? `2px solid ${borderColor}`
      : '1px solid var(--border, #e2e8f0)'

  const boxShadow = isActive
    ? `0 0 0 3px ${ACTIVE_COLOR}33, 0 0 12px ${ACTIVE_COLOR}44`
    : undefined

  return (
    <>
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
      <div
        style={{
          width: 180,
          height: 44,
          borderRadius: 6,
          border,
          boxShadow,
          background: isActive ? '#fef3c710' : 'var(--bg, #fff)',
          display: 'flex',
          alignItems: 'stretch',
          overflow: 'hidden',
          cursor: 'pointer',
        }}
      >
        <div style={{ width: 4, background: fill, flexShrink: 0 }} />
        <div style={{ padding: '4px 8px', overflow: 'hidden', minWidth: 0 }}>
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
      </div>
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
    </>
  )
}

export const DagNode = memo(DagNodeComponent)
