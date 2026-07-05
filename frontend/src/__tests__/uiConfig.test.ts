import { describe, expect, it } from 'vitest'
import {
  DEFAULT_SIDEBAR_CONFIG,
  DEFAULT_TABLE_LAYOUT_CONFIG,
  clamp,
  normalizeSidebarConfig,
  normalizeTableLayoutConfig,
} from '../utils/uiConfig'

describe('uiConfig', () => {
  describe('normalizeSidebarConfig', () => {
    it('uses defaults when config is absent', () => {
      expect(normalizeSidebarConfig()).toEqual(DEFAULT_SIDEBAR_CONFIG)
    })

    it('clamps the default width to configured bounds', () => {
      expect(normalizeSidebarConfig({
        default_width: 120,
        min_width: 220,
        max_width: 560,
      })).toEqual({
        default_width: 220,
        min_width: 220,
        max_width: 560,
        resizable: true,
      })
    })

    it('normalizes max width below min width', () => {
      expect(normalizeSidebarConfig({
        default_width: 260,
        min_width: 360,
        max_width: 240,
        resizable: false,
      })).toEqual({
        default_width: 360,
        min_width: 360,
        max_width: 360,
        resizable: false,
      })
    })
  })

  describe('normalizeTableLayoutConfig', () => {
    it('uses defaults when config is absent', () => {
      expect(normalizeTableLayoutConfig()).toEqual(DEFAULT_TABLE_LAYOUT_CONFIG)
    })

    it('keeps valid table layout mode and min width', () => {
      expect(normalizeTableLayoutConfig({
        mode: 'scroll',
        min_width: 1120,
        content_sized_columns: ['column', 'lineage', 'column'],
        content_sized_max_width: 420,
      })).toEqual({
        mode: 'scroll',
        min_width: 1120,
        content_sized_columns: ['column', 'lineage'],
        content_sized_max_width: 420,
      })
    })

    it('falls back when mode or min width is invalid', () => {
      expect(normalizeTableLayoutConfig({
        mode: 'squish' as never,
        min_width: -1,
        content_sized_columns: 'column' as never,
        content_sized_max_width: -1,
      })).toEqual(DEFAULT_TABLE_LAYOUT_CONFIG)
    })
  })

  it('clamps values to bounds', () => {
    expect(clamp(5, 10, 20)).toBe(10)
    expect(clamp(25, 10, 20)).toBe(20)
    expect(clamp(15, 10, 20)).toBe(15)
  })
})
