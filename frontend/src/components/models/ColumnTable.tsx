import { Fragment, useState, useMemo, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import type { DocglowColumn, ColumnProfile, TopValue, HistogramBin, ColumnLineageDependency, ColumnDownstreamDependency, ColumnLineageData, LineageBadgeConfig } from '../../types'
import { useProjectStore } from '../../stores/projectStore'
import { TestBadge } from '../tests/TestBadge'
import { formatNumber, formatPercent } from '../../utils/formatting'
import { ColumnTraceDrawer } from './ColumnTraceDrawer'
import { ResponsiveTable } from '../ui/ResponsiveTable'
import { normalizeTableLayoutConfig } from '../../utils/uiConfig'
import { applyBadgeAbbreviation } from '../../utils/lineageBadgeAbbreviation'

interface ColumnTableProps {
  columns: DocglowColumn[]
  columnLineage?: Record<string, ColumnLineageDependency[]>
  columnDownstream?: Record<string, ColumnDownstreamDependency[]>
  modelId?: string
  columnLineageData?: ColumnLineageData
}

const TRANSFORMATION_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  passthrough: { label: 'passthrough', color: '#16a34a', bg: '#16a34a14' },
  derived:     { label: 'derived',     color: '#d97706', bg: '#d9770614' },
  aggregated:  { label: 'aggregated',  color: '#7c3aed', bg: '#7c3aed14' },
  unknown:     { label: 'unknown',     color: '#6b7280', bg: '#6b728014' },
  direct:      { label: 'passthrough', color: '#16a34a', bg: '#16a34a14' }, // backward compat
}

const ROLE_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  primary_key: { label: 'PK',         color: '#16a34a', bg: '#16a34a18' },
  foreign_key: { label: 'FK',         color: '#2563eb', bg: '#2563eb18' },
  timestamp:   { label: 'timestamp',  color: '#d97706', bg: '#d9770618' },
  metric:      { label: 'metric',     color: '#7c3aed', bg: '#7c3aed18' },
  categorical: { label: 'categorical',color: '#0891b2', bg: '#0891b218' },
  dimension:   { label: 'dimension',  color: '#6b7280', bg: '#6b728018' },
}

function RoleBadge({ role, confidence }: { role: string; confidence: number }) {
  const style = ROLE_STYLES[role]
  if (!style) return null

  const confColor = confidence >= 0.8 ? '#16a34a' : confidence >= 0.6 ? '#d97706' : '#6b7280'

  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold"
      title={`Inferred role: ${role} (${Math.round(confidence * 100)}% confidence)`}
      style={{ background: style.bg, color: style.color }}
    >
      {style.label}
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ background: confColor }}
      />
    </span>
  )
}

const MAX_BADGES_PER_DIRECTION = 3

const DEFAULT_BADGE_CONFIG: LineageBadgeConfig = {
  abbreviation: 'smart',
  max_model_chars: 30,
  max_column_chars: 22,
}
const COMPACT_BADGE_MAX_CHARS = 36

function NullBar({ rate }: { rate: number }) {
  const color = rate > 0.5 ? 'bg-danger' : rate > 0.1 ? 'bg-warning' : 'bg-success'
  return (
    <div className="flex items-center gap-1.5" title={`${(rate * 100).toFixed(1)}% null`}>
      <div className="w-16 h-1.5 bg-[var(--bg)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${rate * 100}%` }} />
      </div>
      <span className="text-xs text-[var(--text-muted)]">{formatPercent(rate)}</span>
    </div>
  )
}

function TopValuesChart({ values, rowCount }: { values: TopValue[]; rowCount: number }) {
  const maxFreq = Math.max(...values.map(v => v.frequency))
  return (
    <div className="space-y-0.5">
      {values.slice(0, 5).map((v, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-24 truncate font-mono" title={v.value}>{v.value}</span>
          <div className="flex-1 h-1.5 bg-[var(--bg)] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-primary/60"
              style={{ width: `${(v.frequency / maxFreq) * 100}%` }}
            />
          </div>
          <span className="text-[var(--text-muted)] w-8 text-right">{v.frequency}</span>
          {rowCount > 0 && (
            <span className="text-[var(--text-muted)] w-12 text-right">
              {formatPercent(v.frequency / rowCount)}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

function Histogram({ bins }: { bins: HistogramBin[] }) {
  const maxCount = Math.max(...bins.map(b => b.count))
  if (maxCount === 0) return null
  const barHeight = 32

  return (
    <div className="flex items-end gap-px" style={{ height: barHeight }} title="Value distribution">
      {bins.map((bin, i) => {
        const h = maxCount > 0 ? (bin.count / maxCount) * barHeight : 0
        return (
          <div
            key={i}
            className="flex-1 bg-primary/60 rounded-t-sm hover:bg-primary/80 transition-colors"
            style={{ height: `${h}px`, minWidth: 4 }}
            title={`${bin.low.toFixed(1)} – ${bin.high.toFixed(1)}: ${bin.count}`}
          />
        )
      })}
    </div>
  )
}

/** A single directional badge: ← model.col or → model.col */
function LineageBadge({
  modelId,
  columns,
  transformation,
  direction,
}: {
  modelId: string
  columns: string[]
  transformation: string
  direction: 'upstream' | 'downstream'
}) {
  const navigate = useNavigate()
  const [hoverPanel, setHoverPanel] = useState<{ top: number; left: number } | null>(null)
  const badgeConfig = useProjectStore(s => s.data?.ui?.lineage_badge) ?? DEFAULT_BADGE_CONFIG
  const modelName = modelId.split('.').pop() ?? modelId
  const resourceType = modelId.split('.')[0] ?? 'model'
  const navType = resourceType === 'source' ? 'source' : 'model'
  const style = TRANSFORMATION_STYLES[transformation] ?? TRANSFORMATION_STYLES.passthrough
  const colLabel = columns.length === 1 ? columns[0] : `{${columns.join(', ')}}`
  const modelDisplay = applyBadgeAbbreviation(modelName, badgeConfig.max_model_chars, badgeConfig.abbreviation)
  const colDisplay = applyBadgeAbbreviation(colLabel, badgeConfig.max_column_chars, badgeConfig.abbreviation)
  const fullBadgeText = `${modelName}.${colLabel}`
  // Show the detail panel when either side was explicitly abbreviated, or when
  // the combined badge text is too long to fit the fixed pill comfortably.
  const needsDetailPanel =
    modelDisplay !== modelName ||
    colDisplay !== colLabel ||
    fullBadgeText.length > COMPACT_BADGE_MAX_CHARS
  const badgeLabel = `${direction === 'upstream' ? 'From' : 'To'}: ${modelId}; columns: ${columns.join(', ')}; type: ${transformation}`

  const commonButtonProps = {
    onClick: (e: MouseEvent) => {
      e.stopPropagation()
      const colAnchor = columns.length === 1 ? `#col-${columns[0].toLowerCase()}` : ''
      navigate(`/${navType}/${encodeURIComponent(modelId)}${colAnchor}`)
    },
    'aria-label': badgeLabel,
    style: {
      background: style.bg,
      color: style.color,
      borderColor: `${style.color}30`,
    },
  }

  const showHoverPanel = (element: HTMLElement) => {
    const rect = element.getBoundingClientRect()
    const longestLabel = Math.max(modelName.length, colLabel.length + 2)
    const panelWidth = Math.min(360, Math.max(180, longestLabel * 7 + 36), window.innerWidth - 16)
    const left = Math.min(
      Math.max(8, rect.left),
      Math.max(8, window.innerWidth - panelWidth - 8),
    )
    const belowTop = rect.bottom + 6
    const top = belowTop > window.innerHeight - 140 && rect.top > 140
      ? Math.max(8, rect.top - 126)
      : belowTop
    setHoverPanel({ top, left })
  }

  if (!needsDetailPanel) {
    return (
      <button
        {...commonButtonProps}
        className="box-border max-w-[min(260px,100%)] min-w-0 inline-flex flex-row flex-nowrap items-center gap-1
                   rounded border px-1.5 py-0.5 text-[11px] overflow-hidden cursor-pointer text-left
                   transition-all hover:brightness-95"
      >
        {direction === 'upstream' && (
          <span className="shrink-0" style={{ opacity: 0.6, fontSize: 11, lineHeight: 1 }}>
            &#x2190;
          </span>
        )}
        <span className="min-w-0 truncate font-medium">{modelName}</span>
        <span className="min-w-0 truncate" style={{ opacity: 0.7 }}>.{colLabel}</span>
        {direction === 'downstream' && (
          <span className="shrink-0" style={{ opacity: 0.6, fontSize: 11, lineHeight: 1 }}>
            &#x2192;
          </span>
        )}
      </button>
    )
  }

  return (
    <span className="group/lineage-badge relative inline-flex max-w-[min(260px,100%)] min-w-0 align-top">
      <button
        {...commonButtonProps}
        onMouseEnter={(e) => showHoverPanel(e.currentTarget)}
        onFocus={(e) => showHoverPanel(e.currentTarget)}
        onMouseLeave={() => setHoverPanel(null)}
        onBlur={() => setHoverPanel(null)}
        className="box-border w-full max-w-[min(260px,100%)] min-w-0 inline-flex flex-row flex-nowrap items-center gap-1.5
                   rounded border px-[7px] py-[3px] text-[11px] overflow-hidden cursor-pointer text-left
                   transition-[background-color,border-color,filter] duration-200 ease-out
                   hover:brightness-95"
      >
        {direction === 'upstream' && (
          <span
            className="shrink-0"
            style={{ opacity: 0.6, fontSize: 11, lineHeight: 1 }}
          >
            &#x2190;
          </span>
        )}

        <span className="min-w-0 flex-1 overflow-hidden font-medium whitespace-nowrap text-ellipsis">
          {modelDisplay}
        </span>
        <span className="shrink-0" style={{ opacity: 0.7 }}>
          .
        </span>
        <span
          className="min-w-0 flex-initial max-w-[60%] overflow-hidden whitespace-nowrap text-ellipsis"
          style={{ opacity: 0.7 }}
        >
          {colDisplay}
        </span>

        {direction === 'downstream' && (
          <span
            className="shrink-0"
            style={{ opacity: 0.6, fontSize: 11, lineHeight: 1 }}
          >
            &#x2192;
          </span>
        )}
      </button>
      {hoverPanel && typeof document !== 'undefined' && createPortal(
        <div
          data-testid="lineage-badge-detail"
          className="fixed z-[9999] w-fit min-w-[180px] max-w-[min(360px,calc(100vw-16px))]
                     rounded border bg-[var(--bg)] px-2.5 py-2 text-[11px]
                     text-[var(--text)] shadow-xl ring-1 ring-black/5"
          style={{
            top: hoverPanel.top,
            left: hoverPanel.left,
            borderColor: `${style.color}40`,
          }}
        >
          <div className="font-medium [overflow-wrap:anywhere]" style={{ color: style.color }}>
            {modelName}
          </div>
          <div className="mt-1 flex gap-1 [overflow-wrap:anywhere]">
            <span className="shrink-0" style={{ color: style.color }}>&#x21b3;</span>
            <span>{colLabel}</span>
          </div>
        </div>,
        document.body,
      )}
    </span>
  )
}

/** Unified lineage cell showing upstream and downstream in a single column */
function LineageCell({
  upstream,
  downstream,
}: {
  upstream?: ColumnLineageDependency[]
  downstream?: ColumnDownstreamDependency[]
}) {
  const [expandedUp, setExpandedUp] = useState(false)
  const [expandedDown, setExpandedDown] = useState(false)

  const upstreamGrouped = useMemo(() => {
    if (!upstream || upstream.length === 0) return []
    const map = new Map<string, ColumnLineageDependency[]>()
    for (const dep of upstream) {
      const existing = map.get(dep.source_model) ?? []
      map.set(dep.source_model, [...existing, dep])
    }
    return Array.from(map.entries())
  }, [upstream])

  const downstreamGrouped = useMemo(() => {
    if (!downstream || downstream.length === 0) return []
    const map = new Map<string, ColumnDownstreamDependency[]>()
    for (const dep of downstream) {
      const existing = map.get(dep.target_model) ?? []
      map.set(dep.target_model, [...existing, dep])
    }
    return Array.from(map.entries())
  }, [downstream])

  const hasUp = upstreamGrouped.length > 0
  const hasDown = downstreamGrouped.length > 0

  if (!hasUp && !hasDown) {
    return <span className="text-[var(--text-muted)]">—</span>
  }

  const visibleUp = expandedUp ? upstreamGrouped : upstreamGrouped.slice(0, MAX_BADGES_PER_DIRECTION)
  const hiddenUp = upstreamGrouped.length - MAX_BADGES_PER_DIRECTION
  const visibleDown = expandedDown ? downstreamGrouped : downstreamGrouped.slice(0, MAX_BADGES_PER_DIRECTION)
  const hiddenDown = downstreamGrouped.length - MAX_BADGES_PER_DIRECTION

  return (
    <div className="flex max-w-full min-w-0 flex-col gap-1">
      {/* Upstream badges */}
      {hasUp && (
        <div className="flex min-w-0 flex-wrap gap-1 items-center">
          {visibleUp.map(([modelId, modelDeps]) => (
            <LineageBadge
              key={`up-${modelId}`}
              modelId={modelId}
              columns={modelDeps.map(d => d.source_column)}
              transformation={modelDeps[0].transformation}
              direction="upstream"
            />
          ))}
          {!expandedUp && hiddenUp > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpandedUp(true) }}
              className="text-[11px] text-[var(--text-muted)] hover:text-[var(--text)] px-1 cursor-pointer"
            >
              +{hiddenUp} more
            </button>
          )}
        </div>
      )}

      {/* Downstream badges */}
      {hasDown && (
        <div className="flex min-w-0 flex-wrap gap-1 items-center">
          {visibleDown.map(([modelId, modelDeps]) => (
            <LineageBadge
              key={`down-${modelId}`}
              modelId={modelId}
              columns={modelDeps.map(d => d.target_column)}
              transformation={modelDeps[0].transformation}
              direction="downstream"
            />
          ))}
          {!expandedDown && hiddenDown > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpandedDown(true) }}
              className="text-[11px] text-[var(--text-muted)] hover:text-[var(--text)] px-1 cursor-pointer"
            >
              +{hiddenDown} more
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function ProfileDetail({ profile }: { profile: ColumnProfile }) {
  const hasNumeric = profile.mean != null
  const hasString = profile.min_length != null
  const hasDate = profile.min != null && !hasNumeric && !hasString

  return (
    <div className="px-4 py-3 bg-[var(--bg-surface)] border-t border-[var(--border)]">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-[var(--text-muted)]">Rows</span>
          <div className="font-medium">{formatNumber(profile.row_count)}</div>
        </div>
        <div>
          <span className="text-[var(--text-muted)]">Nulls</span>
          <div className="font-medium">
            {formatNumber(profile.null_count)} ({formatPercent(profile.null_rate)})
          </div>
        </div>
        <div>
          <span className="text-[var(--text-muted)]">Distinct</span>
          <div className="font-medium">
            {formatNumber(profile.distinct_count)}
            {profile.is_unique && (
              <span className="ml-1 text-success text-[10px] font-bold">UNIQUE</span>
            )}
          </div>
        </div>
        <div>
          <span className="text-[var(--text-muted)]">Distinct Rate</span>
          <div className="font-medium">{formatPercent(profile.distinct_rate)}</div>
        </div>

        {hasNumeric && (
          <>
            <div>
              <span className="text-[var(--text-muted)]">Min</span>
              <div className="font-medium font-mono">{profile.min ?? '—'}</div>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Max</span>
              <div className="font-medium font-mono">{profile.max ?? '—'}</div>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Mean</span>
              <div className="font-medium font-mono">
                {profile.mean != null ? profile.mean.toFixed(2) : '—'}
              </div>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Median</span>
              <div className="font-medium font-mono">
                {profile.median != null ? profile.median.toFixed(2) : '—'}
              </div>
            </div>
            {profile.stddev != null && (
              <div>
                <span className="text-[var(--text-muted)]">Std Dev</span>
                <div className="font-medium font-mono">{profile.stddev.toFixed(2)}</div>
              </div>
            )}
          </>
        )}

        {hasString && (
          <>
            <div>
              <span className="text-[var(--text-muted)]">Min Length</span>
              <div className="font-medium">{profile.min_length ?? '—'}</div>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Max Length</span>
              <div className="font-medium">{profile.max_length ?? '—'}</div>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Avg Length</span>
              <div className="font-medium">
                {profile.avg_length != null ? profile.avg_length.toFixed(1) : '—'}
              </div>
            </div>
          </>
        )}

        {hasDate && (
          <>
            <div>
              <span className="text-[var(--text-muted)]">Min</span>
              <div className="font-medium font-mono">{String(profile.min)}</div>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Max</span>
              <div className="font-medium font-mono">{String(profile.max)}</div>
            </div>
          </>
        )}
      </div>

      {profile.histogram && profile.histogram.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)] mb-1.5">Distribution</div>
          <Histogram bins={profile.histogram} />
        </div>
      )}

      {profile.top_values && profile.top_values.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)] mb-1.5">Top Values</div>
          <TopValuesChart values={profile.top_values} rowCount={profile.row_count} />
        </div>
      )}
    </div>
  )
}

const CH_PX = 7.2
const BADGE_CH_PX = 6.8
const CELL_X_PADDING = 32
const CHEVRON_WIDTH = 16
const DESCRIPTION_MIN_WIDTH = 340

const FALLBACK_COLUMN_WIDTHS = {
  column: 220,
  type: 160,
  lineage: 360,
  nulls: 120,
  distinct: 96,
  tests: 120,
}

const MIN_CONTENT_SIZED_WIDTHS = {
  column: 160,
  type: 112,
  lineage: 280,
  tests: 120,
}

function clampWidth(value: number, min: number, max: number): number {
  return Math.ceil(Math.max(min, Math.min(max, value)))
}

function maxStringLength(values: readonly string[]): number {
  return values.reduce((max, value) => Math.max(max, value.length), 0)
}

function estimateTestsWidth(columns: readonly DocglowColumn[]): number {
  const widest = columns.reduce((max, column) => {
    if (column.tests.length === 0) return max
    const width = column.tests.reduce((sum, test, index) => {
      const gap = index === 0 ? 0 : 4
      return sum + gap + test.test_type.length * BADGE_CH_PX + 20
    }, 0)
    return Math.max(max, width)
  }, 0)
  return widest + CELL_X_PADDING
}

function modelNameFromId(modelId: string): string {
  return modelId.split('.').pop() ?? modelId
}

function estimateLineageWidth(
  columnLineage?: Record<string, ColumnLineageDependency[]>,
  columnDownstream?: Record<string, ColumnDownstreamDependency[]>,
): number {
  const labels: string[] = []
  for (const deps of Object.values(columnLineage ?? {})) {
    for (const dep of deps) {
      labels.push(`${modelNameFromId(dep.source_model)}.${dep.source_column}`)
    }
  }
  for (const deps of Object.values(columnDownstream ?? {})) {
    for (const dep of deps) {
      labels.push(`${modelNameFromId(dep.target_model)}.${dep.target_column}`)
    }
  }
  return maxStringLength(labels) * BADGE_CH_PX + CELL_X_PADDING + 28
}

export function ColumnTable({ columns, columnLineage, columnDownstream, modelId, columnLineageData }: ColumnTableProps) {
  const [expandedCol, setExpandedCol] = useState<string | null>(null)
  const [traceColumn, setTraceColumn] = useState<string | null>(null)
  const rawTableLayout = useProjectStore(s => s.data?.ui?.table_layout)
  const tableLayout = normalizeTableLayoutConfig(rawTableLayout)
  const canTrace = modelId != null && columnLineageData != null
  const hasAnyProfile = columns.some(c => c.profile != null)
  const hasAnyLineage = (columnLineage != null && Object.keys(columnLineage).length > 0)
    || (columnDownstream != null && Object.keys(columnDownstream).length > 0)

  const layout = useMemo(() => {
    const contentSized = new Set(tableLayout.content_sized_columns)
    const maxContentWidth = Math.max(tableLayout.content_sized_max_width, 1)
    const sized = (
      key: string,
      preferred: number,
      fallback: number,
      min: number,
    ) => contentSized.has(key)
      ? clampWidth(preferred, min, Math.max(maxContentWidth, min))
      : fallback

    const columnPreferred = maxStringLength(columns.map(c => c.name)) * CH_PX
      + CELL_X_PADDING
      + CHEVRON_WIDTH
    const typePreferred = maxStringLength(
      columns.flatMap(c => [c.data_type || '—', c.insights?.semantic_type ?? '']),
    ) * CH_PX + CELL_X_PADDING
    const testsPreferred = estimateTestsWidth(columns)
    const lineagePreferred = estimateLineageWidth(columnLineage, columnDownstream)

    const columnWidth = sized(
      'column',
      columnPreferred,
      FALLBACK_COLUMN_WIDTHS.column,
      MIN_CONTENT_SIZED_WIDTHS.column,
    )
    const typeWidth = sized(
      'type',
      typePreferred,
      FALLBACK_COLUMN_WIDTHS.type,
      MIN_CONTENT_SIZED_WIDTHS.type,
    )
    const lineageWidth = sized(
      'lineage',
      lineagePreferred,
      FALLBACK_COLUMN_WIDTHS.lineage,
      MIN_CONTENT_SIZED_WIDTHS.lineage,
    )
    const testsWidth = sized(
      'tests',
      testsPreferred,
      FALLBACK_COLUMN_WIDTHS.tests,
      MIN_CONTENT_SIZED_WIDTHS.tests,
    )
    const tableMinWidth = columnWidth
      + typeWidth
      + DESCRIPTION_MIN_WIDTH
      + testsWidth
      + (hasAnyLineage ? lineageWidth : 0)
      + (hasAnyProfile ? FALLBACK_COLUMN_WIDTHS.nulls + FALLBACK_COLUMN_WIDTHS.distinct : 0)

    return {
      columnWidth,
      typeWidth,
      lineageWidth,
      testsWidth,
      tableMinWidth,
    }
  }, [
    columns,
    columnDownstream,
    columnLineage,
    hasAnyLineage,
    hasAnyProfile,
    tableLayout.content_sized_columns,
    tableLayout.content_sized_max_width,
  ])

  const totalCols = 4
    + (hasAnyProfile ? 2 : 0)
    + (hasAnyLineage ? 1 : 0)

  if (columns.length === 0) {
    return <div className="text-sm text-[var(--text-muted)]">No columns found.</div>
  }

  return (
    <>
      <ResponsiveTable defaultMinWidth={layout.tableMinWidth} tableClassName="table-fixed">
        <colgroup>
          <col style={{ width: layout.columnWidth }} />
          <col style={{ width: layout.typeWidth }} />
          <col />
          {hasAnyLineage && <col style={{ width: layout.lineageWidth }} />}
          {hasAnyProfile && (
            <>
              <col style={{ width: FALLBACK_COLUMN_WIDTHS.nulls }} />
              <col style={{ width: FALLBACK_COLUMN_WIDTHS.distinct }} />
            </>
          )}
          <col style={{ width: layout.testsWidth }} />
        </colgroup>
        <thead className="bg-[var(--bg-surface)]">
          <tr>
            <th className="text-left px-4 py-2 font-medium whitespace-nowrap">Column</th>
            <th className="text-left px-4 py-2 font-medium whitespace-nowrap">Type</th>
            <th className="text-left px-4 py-2 font-medium">Description</th>
            {hasAnyLineage && (
              <th className="text-left px-4 py-2 font-medium">
                <span>Lineage</span>
                <span className="ml-1.5 text-[10px] text-[var(--text-muted)] font-normal">← sources  → consumers</span>
              </th>
            )}
            {hasAnyProfile && (
              <>
                <th className="text-left px-4 py-2 font-medium">Nulls</th>
                <th className="text-right px-4 py-2 font-medium">Distinct</th>
              </>
            )}
            <th className="text-left px-4 py-2 font-medium whitespace-nowrap">Tests</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => {
            const isExpanded = expandedCol === col.name
            const canExpand = col.profile != null
            const upDeps = columnLineage?.[col.name]
            const downDeps = columnDownstream?.[col.name]
            return (
              <Fragment key={col.name}>
                <tr
                  id={`col-${col.name}`}
                  className={`group ${canExpand ? 'cursor-pointer hover:bg-[var(--bg-surface)]' : ''}
                    ${isExpanded ? 'bg-[var(--bg-surface)]' : ''}`}
                  onClick={() => canExpand && setExpandedCol(isExpanded ? null : col.name)}
                >
                  <td className="border-t border-[var(--border)] align-top px-4 py-2 font-mono text-xs font-medium">
                    <div className="flex min-w-0 items-start">
                      {canExpand && (
                        <svg
                          className={`w-3 h-3 shrink-0 mr-1 mt-0.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                          fill="currentColor" viewBox="0 0 20 20"
                        >
                          <path fillRule="evenodd"
                                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                                clipRule="evenodd" />
                        </svg>
                      )}
                      <div className="min-w-0">
                        <span
                          className="block [overflow-wrap:anywhere] [word-break:normal]"
                          title={col.name}
                        >
                          {col.name}
                        </span>
                        {col.insights?.role && (
                          <div className="mt-0.5">
                            <RoleBadge role={col.insights.role} confidence={col.insights.confidence} />
                          </div>
                        )}
                      </div>
                    </div>
                  </td>

                  <td className="border-t border-[var(--border)] align-top px-4 py-2 font-mono text-xs text-[var(--text-muted)] uppercase [overflow-wrap:anywhere]">
                    <div title={col.data_type || '—'}>
                      {col.data_type || '—'}
                    </div>
                    {col.insights?.semantic_type && (
                      <div
                        className="text-[9px] normal-case opacity-60 mt-0.5"
                        title={col.insights.semantic_type}
                      >
                        {col.insights.semantic_type}
                      </div>
                    )}
                  </td>

                  <td className="border-t border-[var(--border)] align-top px-4 py-2 min-w-0">
                    {col.description ? (
                      <span
                        title={col.description}
                        className="text-sm leading-snug block [overflow-wrap:anywhere]"
                      >
                        {col.description}
                        {col.insights?.generated_description && col.description === col.insights.generated_description && (
                          <span className="ml-1.5 text-[9px] text-[var(--text-muted)] opacity-60 font-medium uppercase">auto</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-sm text-[var(--text-muted)] italic">No description</span>
                    )}
                    {col.insights?.sql_usage && col.insights.sql_usage.length > 0 && !col.insights.sql_usage.every(u => u === 'selected_only') && (
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {col.insights.sql_usage.filter(u => u !== 'selected_only').map(usage => (
                          <span key={usage} className="text-[9px] text-[var(--text-muted)] opacity-70">
                            {usage.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>

                  {hasAnyLineage && (
                    <td className="border-t border-[var(--border)] align-top px-4 py-1.5 min-w-0">
                      <div className="flex min-w-0 items-start gap-1.5">
                        <div className="min-w-0 flex-1">
                          <LineageCell upstream={upDeps} downstream={downDeps} />
                        </div>
                        {canTrace && (upDeps || downDeps) && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setTraceColumn(col.name)
                            }}
                            className="shrink-0 p-1 rounded hover:bg-[var(--bg-surface)] cursor-pointer
                                       transition-colors text-[var(--text-muted)] hover:text-[var(--text)]"
                            title="View full column trace"
                          >
                            <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                              <path d="M7 17L17 7M7 7h10v10" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                  )}

                  {hasAnyProfile && (
                    <>
                      <td className="border-t border-[var(--border)] align-top px-4 py-2">
                        {col.profile ? (
                          <NullBar rate={col.profile.null_rate} />
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>
                      <td className="border-t border-[var(--border)] align-top px-4 py-2 text-right">
                        {col.profile ? (
                          <span className="text-xs" title={`${col.profile.distinct_count} distinct`}>
                            {formatNumber(col.profile.distinct_count)}
                            {col.profile.is_unique && (
                              <span className="ml-1 text-success text-[10px]">U</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>
                    </>
                  )}

                  <td className="border-t border-[var(--border)] align-top px-4 py-2">
                    {col.tests.length > 0 ? (
                      <div className="flex min-w-0 flex-wrap gap-1">
                        {col.tests.map((test, i) => (
                          <TestBadge key={i} status={test.status} label={test.test_type} />
                        ))}
                      </div>
                    ) : (
                      <span className="text-[var(--text-muted)]">—</span>
                    )}
                  </td>
                </tr>
                {isExpanded && col.profile && (
                  <tr className="bg-[var(--bg-surface)]">
                    <td colSpan={totalCols} className="p-0">
                      <ProfileDetail profile={col.profile} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </ResponsiveTable>
      {traceColumn && canTrace && (
        <ColumnTraceDrawer
          modelId={modelId}
          columnName={traceColumn}
          columnLineageData={columnLineageData}
          onClose={() => setTraceColumn(null)}
        />
      )}
    </>
  )
}
