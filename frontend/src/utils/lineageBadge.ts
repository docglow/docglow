import type { LineageBadgeConfig } from '../types'

// Longest `model.column` text that fits the pill without being clipped.
const COMPACT_BADGE_MAX_CHARS = 36

/** Whether a badge has more to reveal on hover than its compact form shows. */
export function badgeHasHoverDetail(
  names: { modelName: string; modelDisplay: string; colLabel: string; colDisplay: string },
  hoverDetail: LineageBadgeConfig['hover_detail'],
): boolean {
  const { modelName, modelDisplay, colLabel, colDisplay } = names
  const isAbbreviated = modelDisplay !== modelName || colDisplay !== colLabel
  if (hoverDetail !== 'panel') return isAbbreviated
  return isAbbreviated || `${modelName}.${colLabel}`.length > COMPACT_BADGE_MAX_CHARS
}

export interface BadgePanelPosition {
  readonly left: number
  readonly top?: number
  readonly bottom?: number
}

/** Place the panel under the badge, or above it when the viewport has no room below. */
export function badgePanelPosition(
  anchor: { readonly left: number; readonly top: number; readonly bottom: number },
  viewport: { readonly width: number; readonly height: number },
  longestLabel: number,
): BadgePanelPosition {
  const gap = 6
  const roomNeeded = 140
  const panelWidth = Math.min(360, Math.max(180, longestLabel * 7 + 36), viewport.width - 16)
  const left = Math.min(Math.max(8, anchor.left), Math.max(8, viewport.width - panelWidth - 8))
  const flipAbove = anchor.bottom + gap > viewport.height - roomNeeded && anchor.top > roomNeeded
  return flipAbove
    ? { left, bottom: viewport.height - anchor.top + gap }
    : { left, top: anchor.bottom + gap }
}
