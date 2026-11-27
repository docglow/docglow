/**
 * ErdEdge — React Flow custom edge type (`edgeType: 'erdRelationship'`).
 *
 * Receives `sourceX/Y/targetX/Y/sourcePosition/targetPosition` resolved by
 * React Flow from the source/target handles declared on `ErdNode`. The
 * crow's-foot glyph layer is rendered manually because React Flow's built-in
 * markers don't cover the four ERD endpoint shapes.
 *
 * Visual reference: `examples/erd-design-examples/erd-shared.jsx` (`EdgeLayer`,
 * `CrowsFoot`, `buildEdgePath`).
 *
 * Crow's-foot glyph mapping (origin requirements §5.3):
 *   - one_and_only_one  → `||`
 *   - zero_or_one       → `o|`
 *   - one_or_many       → `}|`
 *   - zero_or_many      → `}o`
 *
 * Lanes: the H-V-H path turns at `data.lane`'s x within the gap (see
 * `utils/erdEdgeLanes.ts`), so edges sharing a gap each get their own
 * vertical segment instead of merging into one trunk.
 *
 * Special cases:
 *   - Self-referential FK (`from_unique_id === to_unique_id`): curved Bezier
 *     loop instead of an orthogonal H-V-H path. Glyphs suppressed because the
 *     curved geometry doesn't read with horizontal glyphs.
 *   - Ghost edge (`parent_column_exists === false` OR `to_unique_id === ''`):
 *     dashed gray. ErdCanvas filters these out before they reach this
 *     component (matches v1 behavior); kept here for resilience.
 */

import { useCallback } from 'react'
import { Position, type EdgeProps } from '@xyflow/react'
import type { ErdEndpoint, ErdRelationship, ErdStatus } from '../../types'
import { laneX, type EdgeLane } from '../../utils/erdEdgeLanes'

export interface ErdEdgeData {
  readonly rel: ErdRelationship
  readonly selected?: boolean
  /**
   * This edge's vertical lane within its channel, assigned by `ErdCanvas`
   * via `assignEdgeLanes`. Absent → turn at the gap midpoint.
   */
  readonly lane?: EdgeLane
}

const STATUS_COLOR: Record<ErdStatus, string> = {
  pass: '#16a34a',
  fail: '#dc2626',
  warn: '#d97706',
  not_run: '#64748b',
  none: '#64748b',
}

const SELECTED_COLOR = '#f59e0b'
const GHOST_COLOR = '#94a3b8'

/** How far outside the anchor the crow's-foot glyph sits.
 * Bumped from 8 → 10 (DOC-99 follow-up) so the inner/outer glyphs have a bit
 * more breathing room when two edges share the same column row anchor. */
const GLYPH_OFFSET = 10
/** Half-height of the perpendicular bar / fork. */
const GLYPH_HALF = 5
/** Radius of the open circle in `zero_or_*` glyphs. */
const GLYPH_CIRCLE_R = 3

function buildOrthogonalPath(
  from: { x: number; y: number },
  to: { x: number; y: number },
  lane: EdgeLane | undefined,
): string {
  const turnX = laneX(lane, from.x, to.x)
  return `M ${from.x} ${from.y} H ${turnX} V ${to.y} H ${to.x}`
}

function buildSelfLoopPath(
  from: { x: number; y: number },
  to: { x: number; y: number },
): string {
  const c1x = from.x + 60
  const c1y = from.y - 30
  const c2x = from.x + 60
  const c2y = to.y + 30
  return `M ${from.x} ${from.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${to.x} ${to.y}`
}

interface CrowsFootProps {
  readonly endpoint: ErdEndpoint
  readonly anchor: { readonly x: number; readonly y: number }
  readonly side: 'left' | 'right'
  readonly stroke: string
  readonly opacity?: number
}

function CrowsFoot({ endpoint, anchor, side, stroke, opacity = 1 }: CrowsFootProps) {
  const dir = side === 'right' ? 1 : -1
  const innerX = anchor.x + dir * GLYPH_OFFSET
  const outerX = anchor.x + dir * GLYPH_OFFSET * 2

  // Standard crow's-foot notation (Wikipedia):
  //   - INNER glyph (closer to the table edge) carries the CARDINALITY:
  //       fork ("crow's foot") for "many", bar for "one".
  //   - OUTER glyph (further along the line, back from the table) carries
  //     the OPTIONALITY: circle for "zero allowed", bar for "mandatory".
  // The fork's vertex sits at innerX (back from the table) and the three
  // prongs converge AT the table edge (anchor.x), so the foot "opens up"
  // toward the table.
  const innerKind: 'bar' | 'fork' =
    endpoint === 'one_or_many' || endpoint === 'zero_or_many' ? 'fork' : 'bar'
  const outerKind: 'bar' | 'circle' =
    endpoint === 'zero_or_one' || endpoint === 'zero_or_many' ? 'circle' : 'bar'

  const renderPrimitive = (kind: 'bar' | 'circle' | 'fork', x: number, key: string) => {
    if (kind === 'bar') {
      return (
        <line
          key={key}
          x1={x}
          y1={anchor.y - GLYPH_HALF}
          x2={x}
          y2={anchor.y + GLYPH_HALF}
          stroke={stroke}
          strokeWidth={1.5}
          opacity={opacity}
          strokeLinecap="round"
        />
      )
    }
    if (kind === 'circle') {
      return (
        <circle
          key={key}
          cx={x}
          cy={anchor.y}
          r={GLYPH_CIRCLE_R}
          fill="var(--bg, #fff)"
          stroke={stroke}
          strokeWidth={1.5}
          opacity={opacity}
        />
      )
    }
    // Fork: vertex at `x` (= innerX, back from the table along the line);
    // three prongs converge AT the table edge (`anchor.x`) with vertical
    // spread `± GLYPH_HALF`. The foot opens toward the table.
    return (
      <g key={key} stroke={stroke} strokeWidth={1.25} opacity={opacity} fill="none">
        <line x1={x} y1={anchor.y} x2={anchor.x} y2={anchor.y - GLYPH_HALF} />
        <line x1={x} y1={anchor.y} x2={anchor.x} y2={anchor.y} />
        <line x1={x} y1={anchor.y} x2={anchor.x} y2={anchor.y + GLYPH_HALF} />
      </g>
    )
  }

  return (
    <g>
      {renderPrimitive(outerKind, outerX, 'outer')}
      {renderPrimitive(innerKind, innerX, 'inner')}
    </g>
  )
}

/**
 * Map React Flow's `Position` enum → our left/right side string. The ERD
 * handles only ever sit on Left or Right; Top/Bottom would mean the canvas
 * has been mis-wired.
 */
function positionToSide(p: Position): 'left' | 'right' {
  return p === Position.Left ? 'left' : 'right'
}

/**
 * Custom React Flow edge. Receives source/target coordinates already resolved
 * by React Flow from the chosen handle IDs.
 */
export function ErdEdge(props: EdgeProps) {
  const {
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    data,
    selected: rfSelected,
    source,
    target,
  } = props
  const edgeData = data as ErdEdgeData | undefined
  const rel = edgeData?.rel
  // Prefer data.selected when present (canvas-managed); fall back to React
  // Flow's built-in `selected`. ErdCanvas drives selection via data, so
  // both will be in sync in practice.
  const selected = edgeData?.selected ?? rfSelected ?? false

  const isGhost =
    !!rel && (rel.parent_column_exists === false || rel.to_unique_id === '')
  const isSelfRef = source === target && source !== ''

  const baseStroke = isGhost
    ? GHOST_COLOR
    : (rel ? (STATUS_COLOR[rel.status] ?? STATUS_COLOR.none) : STATUS_COLOR.none)
  const stroke = selected ? SELECTED_COLOR : baseStroke
  const strokeWidth = selected ? 2 : 1.25
  const dasharray = isGhost ? '4 4' : undefined

  const fromAnchor = { x: sourceX, y: sourceY }
  const toAnchor = { x: targetX, y: targetY }

  const path = isSelfRef
    ? buildSelfLoopPath(fromAnchor, toAnchor)
    : buildOrthogonalPath(fromAnchor, toAnchor, edgeData?.lane)

  const fromSide = positionToSide(sourcePosition)
  const toSide = positionToSide(targetPosition)

  // React Flow already wires onClick via onEdgeClick at the canvas level;
  // we keep a no-op onClick here only if `data.onSelect` is provided
  // (none currently — left for symmetry with the previous API).
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      // Don't stop propagation — React Flow's onEdgeClick handles routing.
      void e
    },
    [],
  )

  return (
    <g
      id={`erd-edge-${id}`}
      data-erd-edge-id={id}
      style={{ pointerEvents: 'auto', cursor: 'pointer' }}
      onClick={handleClick}
    >
      {/* Wide invisible hit-path for click target. */}
      <path d={path} stroke="transparent" strokeWidth={14} fill="none" />
      {/* Visible edge line. */}
      <path
        d={path}
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeDasharray={dasharray}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Crow's-foot glyphs.
          Per origin requirements §5.3, `child_endpoint` is the child's-POV
          cardinality ("toward parent") — drawn AT the parent's end of the
          line (toAnchor). `parent_endpoint` is the parent's-POV cardinality
          ("toward child") — drawn AT the child's end (fromAnchor). This
          yields standard Wikipedia crow's-foot orientation: the bar (||)
          sits on the one/PK side, the fork (}|) on the many/FK side.
          (The edge `source` is the child/FK and `target` is the parent/PK,
          set by ErdCanvas — fromAnchor=child end, toAnchor=parent end.)
          Suppressed for ghost edges (no parent to mark) and self-loops (the
          curved geometry doesn't read with horizontal glyphs). */}
      {!isGhost && !isSelfRef && rel && (
        <>
          {/* child's POV (e.g. "exactly one parent") drawn at the parent end */}
          <CrowsFoot
            endpoint={rel.child_endpoint}
            anchor={toAnchor}
            side={toSide}
            stroke={stroke}
          />
          {/* parent's POV (e.g. "one or many children") drawn at the child end */}
          <CrowsFoot
            endpoint={rel.parent_endpoint}
            anchor={fromAnchor}
            side={fromSide}
            stroke={stroke}
          />
        </>
      )}
    </g>
  )
}
