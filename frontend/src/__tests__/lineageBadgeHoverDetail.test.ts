import { describe, it, expect } from 'vitest'
import { badgeHasHoverDetail, badgePanelPosition } from '../utils/lineageBadge'

/* vitest runs in `node` with no testing library, so the option is exercised
   through the pure helpers. e2e/lineage-badge.spec.ts covers the rendered modes. */

const short = { modelName: 'orders', modelDisplay: 'orders', colLabel: 'id', colDisplay: 'id' }
const abbreviated = { ...short, modelDisplay: 'ord…' }
// Nothing shortened, but `model.column` is longer than the pill can show.
const longButUnshortened = {
  modelName: 'customer_orders_by_region',
  modelDisplay: 'customer_orders_by_region',
  colLabel: 'lifetime_value_usd',
  colDisplay: 'lifetime_value_usd',
}

describe('badgeHasHoverDetail', () => {
  it('reveals detail only for shortened names when the option is absent or inline', () => {
    for (const mode of [undefined, 'inline'] as const) {
      expect(badgeHasHoverDetail(short, mode)).toBe(false)
      expect(badgeHasHoverDetail(abbreviated, mode)).toBe(true)
      expect(badgeHasHoverDetail(longButUnshortened, mode)).toBe(false)
    }
  })

  it('panel mode also reveals detail when the combined text is too long for the pill', () => {
    expect(badgeHasHoverDetail(short, 'panel')).toBe(false)
    expect(badgeHasHoverDetail(abbreviated, 'panel')).toBe(true)
    expect(badgeHasHoverDetail(longButUnshortened, 'panel')).toBe(true)
  })
})

describe('badgePanelPosition', () => {
  const viewport = { width: 1280, height: 720 }

  it('opens below the badge when there is room', () => {
    const anchor = { left: 200, top: 100, bottom: 120 }
    expect(badgePanelPosition(anchor, viewport, 20)).toEqual({ left: 200, top: 126 })
  })

  it('anchors above the badge when the viewport has no room below', () => {
    const anchor = { left: 200, top: 660, bottom: 680 }
    expect(badgePanelPosition(anchor, viewport, 20)).toEqual({ left: 200, bottom: 66 })
  })

  it('keeps the panel inside the right edge', () => {
    const anchor = { left: 1270, top: 100, bottom: 120 }
    // Widest panel is 360px, so left stops at 1280 - 360 - 8.
    expect(badgePanelPosition(anchor, viewport, 80).left).toBe(912)
  })

  it('stays in the viewport on very narrow screens', () => {
    const anchor = { left: 2, top: 100, bottom: 120 }
    expect(badgePanelPosition(anchor, { width: 180, height: 720 }, 80).left).toBe(8)
  })
})
