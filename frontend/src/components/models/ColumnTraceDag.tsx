import { useMemo, useCallback, useEffect, useRef } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  type NodeTypes,
} from '@xyflow/react'
import type { ColumnEdge } from '../../types'
import { buildTraceLayout } from '../../utils/columnTraceLayout'
import { ColumnTraceNode } from './ColumnTraceNode'

interface ColumnTraceDagProps {
  readonly traceEdges: readonly ColumnEdge[]
  readonly currentModelId: string
  readonly currentColumn: string
  /** Toggling this value re-fits the graph to the (resized) container. */
  readonly fitSignal?: boolean
}

const nodeTypes: NodeTypes = {
  columnTrace: ColumnTraceNode,
}

function ColumnTraceDagInner({
  traceEdges,
  currentModelId,
  currentColumn,
  fitSignal,
}: ColumnTraceDagProps) {
  const { fitView } = useReactFlow()

  const { nodes, edges } = useMemo(
    () => buildTraceLayout(traceEdges, currentModelId, currentColumn),
    [traceEdges, currentModelId, currentColumn],
  )

  const onInit = useCallback(() => {
    // Small delay to let nodes render before fitting
    requestAnimationFrame(() => fitView({ padding: 0.2 }))
  }, [fitView])

  // Re-fit when the container resizes (e.g. entering/exiting fullscreen).
  // Skip the initial mount — onInit already handles the first fit.
  const isFirstFit = useRef(true)
  useEffect(() => {
    if (isFirstFit.current) {
      isFirstFit.current = false
      return
    }
    // Wait for the CSS-driven resize to settle before fitting.
    const id = requestAnimationFrame(() =>
      requestAnimationFrame(() => fitView({ padding: 0.2 })),
    )
    return () => cancelAnimationFrame(id)
  }, [fitSignal, fitView])

  if (nodes.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: 'var(--text-muted, #64748b)',
          fontSize: 13,
        }}
      >
        No lineage edges to display
      </div>
    )
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onInit={onInit}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.3}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
    >
      <Background variant={BackgroundVariant.Dots} gap={16} size={0.5} />
      <Controls
        showInteractive={false}
        position="bottom-right"
        style={{ borderRadius: 6 }}
      />
    </ReactFlow>
  )
}

export function ColumnTraceDag(props: ColumnTraceDagProps) {
  return (
    <ReactFlowProvider>
      <ColumnTraceDagInner {...props} />
    </ReactFlowProvider>
  )
}
