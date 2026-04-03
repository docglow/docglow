import { useEffect, useCallback, useMemo } from 'react'
import type { ColumnEdge, ColumnLineageData } from '../../types'
import {
  getColumnTraceResult,
  buildReverseIndex,
} from '../../utils/columnLineageGraph'
import { ColumnTraceDag } from './ColumnTraceDag'

const TRANSFORMATION_STYLES: Record<string, { label: string; color: string }> = {
  passthrough: { label: 'Passthrough', color: '#16a34a' },
  derived:     { label: 'Derived',     color: '#d97706' },
  aggregated:  { label: 'Aggregated',  color: '#7c3aed' },
  unknown:     { label: 'Unknown',     color: '#6b7280' },
  direct:      { label: 'Passthrough', color: '#16a34a' },
  rename:      { label: 'Rename',      color: '#d97706' },
}

interface ColumnTraceDrawerProps {
  readonly modelId: string
  readonly columnName: string
  readonly columnLineageData: ColumnLineageData
  readonly onClose: () => void
}

export function ColumnTraceDrawer({
  modelId,
  columnName,
  columnLineageData,
  onClose,
}: ColumnTraceDrawerProps) {
  // Close on Escape
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose],
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const reverseIndex = useMemo(
    () => buildReverseIndex(columnLineageData),
    [columnLineageData],
  )

  const traceResult = useMemo(
    () => getColumnTraceResult(modelId, columnName, columnLineageData, reverseIndex),
    [modelId, columnName, columnLineageData, reverseIndex],
  )

  const stats = useMemo(() => {
    const models = new Set<string>()
    for (const edge of traceResult.edges) {
      models.add(edge.sourceModel)
      models.add(edge.targetModel)
    }
    // Count upstream vs downstream edges
    const upEdges = countUpstreamEdges(traceResult.edges, modelId)
    const downEdges = traceResult.edges.length - upEdges
    return { modelCount: models.size, upEdges, downEdges }
  }, [traceResult.edges, modelId])

  const modelName = modelId.split('.').pop() ?? modelId

  // Collect unique transformation types used in this trace
  const usedTransformations = useMemo(() => {
    const types = new Set<string>()
    for (const edge of traceResult.edges) {
      types.add(edge.transformation)
    }
    return [...types].sort()
  }, [traceResult.edges])

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,0.4)',
        }}
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          width: 'clamp(500px, 50vw, 800px)',
          height: '100%',
          background: 'var(--bg, #fff)',
          borderLeft: '1px solid var(--border, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            flexShrink: 0,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: 'var(--text, #0f172a)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              Column Trace: {modelName}.{columnName}
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--text-muted, #64748b)',
                marginTop: 2,
              }}
            >
              {stats.upEdges} upstream · {stats.downEdges} downstream · {stats.modelCount} models
            </div>
          </div>

          {/* Close button */}
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              color: 'var(--text-muted, #64748b)',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
            title="Close (Esc)"
          >
            <svg
              width={20}
              height={20}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* DAG body */}
        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <ColumnTraceDag
            traceEdges={traceResult.edges}
            currentModelId={modelId}
            currentColumn={columnName}
          />
        </div>

        {/* Legend footer */}
        {usedTransformations.length > 0 && (
          <div
            style={{
              padding: '10px 20px',
              borderTop: '1px solid var(--border, #e2e8f0)',
              display: 'flex',
              gap: 16,
              alignItems: 'center',
              flexShrink: 0,
              flexWrap: 'wrap',
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-muted, #64748b)',
                fontWeight: 500,
              }}
            >
              Transformations:
            </span>
            {usedTransformations.map((type) => {
              const style = TRANSFORMATION_STYLES[type] ?? TRANSFORMATION_STYLES.unknown
              return (
                <div
                  key={type}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 11,
                  }}
                >
                  <div
                    style={{
                      width: 16,
                      height: 3,
                      borderRadius: 2,
                      background: style.color,
                    }}
                  />
                  <span style={{ color: 'var(--text, #0f172a)' }}>{style.label}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Count edges that are upstream of the given model.
 * An edge is upstream if its target eventually leads to currentModelId.
 */
function countUpstreamEdges(
  edges: readonly ColumnEdge[],
  currentModelId: string,
): number {
  // Build set of models that are upstream (their edges feed into currentModelId)
  const upstreamModels = new Set<string>()
  upstreamModels.add(currentModelId)

  // Iteratively expand: if an edge targets an upstream model, its source is also upstream
  let changed = true
  while (changed) {
    changed = false
    for (const edge of edges) {
      if (upstreamModels.has(edge.targetModel) && !upstreamModels.has(edge.sourceModel)) {
        upstreamModels.add(edge.sourceModel)
        changed = true
      }
    }
  }

  // Count edges where both source and target are in the upstream set
  // and the target is the current model or feeds into it
  return edges.filter(
    (e) => upstreamModels.has(e.sourceModel) && upstreamModels.has(e.targetModel),
  ).length
}

