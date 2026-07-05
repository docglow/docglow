import type { SidebarConfig, TableLayoutConfig, TableLayoutMode } from '../types'

export const DEFAULT_SIDEBAR_CONFIG: SidebarConfig = {
  default_width: 256,
  min_width: 180,
  max_width: 480,
  resizable: true,
}

export const DEFAULT_TABLE_LAYOUT_CONFIG: TableLayoutConfig = {
  mode: 'auto',
  min_width: null,
  content_sized_columns: ['column', 'type', 'tests'],
  content_sized_max_width: 360,
}

function positiveNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null
}

function normalizeStringList(value: unknown, fallback: readonly string[]): readonly string[] {
  if (!Array.isArray(value)) return fallback
  const normalized = value
    .filter((item): item is string => typeof item === 'string')
    .map(item => item.trim().toLowerCase())
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function normalizeSidebarConfig(config?: Partial<SidebarConfig> | null): SidebarConfig {
  const min_width = positiveNumber(config?.min_width) ?? DEFAULT_SIDEBAR_CONFIG.min_width
  let max_width = positiveNumber(config?.max_width) ?? DEFAULT_SIDEBAR_CONFIG.max_width
  if (max_width < min_width) max_width = min_width

  const rawDefault = positiveNumber(config?.default_width) ?? DEFAULT_SIDEBAR_CONFIG.default_width

  return {
    default_width: clamp(rawDefault, min_width, max_width),
    min_width,
    max_width,
    resizable: typeof config?.resizable === 'boolean'
      ? config.resizable
      : DEFAULT_SIDEBAR_CONFIG.resizable,
  }
}

export function normalizeTableLayoutConfig(
  config?: Partial<TableLayoutConfig> | null,
): TableLayoutConfig {
  const mode: TableLayoutMode =
    config?.mode === 'scroll' || config?.mode === 'fit' || config?.mode === 'auto'
      ? config.mode
      : DEFAULT_TABLE_LAYOUT_CONFIG.mode

  return {
    mode,
    min_width: positiveNumber(config?.min_width),
    content_sized_columns: normalizeStringList(
      config?.content_sized_columns,
      DEFAULT_TABLE_LAYOUT_CONFIG.content_sized_columns,
    ),
    content_sized_max_width:
      positiveNumber(config?.content_sized_max_width)
      ?? DEFAULT_TABLE_LAYOUT_CONFIG.content_sized_max_width,
  }
}
