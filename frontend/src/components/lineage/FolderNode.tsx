import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

export interface FolderNodeData {
  name: string
  modelCount: number
  sourceCount: number
  isExpanded: boolean
  [key: string]: unknown
}

function FolderNodeComponent({ data }: NodeProps) {
  const { name, modelCount, sourceCount, isExpanded } = data as FolderNodeData

  const parts: string[] = []
  if (modelCount > 0) parts.push(`${modelCount} model${modelCount !== 1 ? 's' : ''}`)
  if (sourceCount > 0) parts.push(`${sourceCount} source${sourceCount !== 1 ? 's' : ''}`)
  const total = modelCount + sourceCount

  return (
    <>
      <Handle type="target" position={Position.Left} className="!opacity-0 !w-0 !h-0" />
      <div
        style={{
          width: 220,
          height: 60,
          borderRadius: 8,
          border: '1.5px dashed var(--border, #e2e8f0)',
          background: 'var(--bg-surface, #f8fafc)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '0 12px',
          cursor: 'pointer',
        }}
      >
        {/* Folder icon */}
        <svg
          width={20}
          height={20}
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--text-muted, #64748b)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ flexShrink: 0 }}
        >
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
        </svg>

        <div style={{ overflow: 'hidden', minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 13,
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
            {parts.join(' · ')} ({total})
          </div>
        </div>

        {/* Expand/collapse chevron */}
        <svg
          width={14}
          height={14}
          viewBox="0 0 20 20"
          fill="var(--text-muted, #64748b)"
          style={{
            flexShrink: 0,
            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
            transition: 'transform 0.15s ease',
          }}
        >
          <path
            fillRule="evenodd"
            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
            clipRule="evenodd"
          />
        </svg>
      </div>
      <Handle type="source" position={Position.Right} className="!opacity-0 !w-0 !h-0" />
    </>
  )
}

export const FolderNode = memo(FolderNodeComponent)
