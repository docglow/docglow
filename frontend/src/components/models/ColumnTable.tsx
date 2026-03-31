import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { DocglowColumn, ColumnProfile, TopValue, HistogramBin, ColumnLineageDependency, ColumnDownstreamDependency } from '../../types'
import { TestBadge } from '../tests/TestBadge'
import { formatNumber, formatPercent } from '../../utils/formatting'

interface ColumnTableProps {
  columns: DocglowColumn[]
  columnLineage?: Record<string, ColumnLineageDependency[]>
  columnDownstream?: Record<string, ColumnDownstreamDependency[]>
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
  const modelName = modelId.split('.').pop() ?? modelId
  const resourceType = modelId.split('.')[0] ?? 'model'
  const navType = resourceType === 'source' ? 'source' : 'model'
  const style = TRANSFORMATION_STYLES[transformation] ?? TRANSFORMATION_STYLES.passthrough
  const colLabel = columns.length === 1 ? columns[0] : `{${columns.join(', ')}}`

  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        const colAnchor = columns.length === 1 ? `#col-${columns[0].toLowerCase()}` : ''
        navigate(`/${navType}/${encodeURIComponent(modelId)}${colAnchor}`)
      }}
      title={`${direction === 'upstream' ? 'From' : 'To'}: ${modelId}\nColumns: ${columns.join(', ')}\nType: ${transformation}`}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px]
                 hover:brightness-90 transition-all cursor-pointer border"
      style={{
        background: style.bg,
        color: style.color,
        borderColor: `${style.color}30`,
      }}
    >
      {direction === 'upstream' && (
        <span style={{ opacity: 0.6, fontSize: 11, lineHeight: 1 }}>&#x2190;</span>
      )}
      <span className="font-medium">{modelName}</span>
      <span style={{ opacity: 0.7 }}>.{colLabel}</span>
      {direction === 'downstream' && (
        <span style={{ opacity: 0.6, fontSize: 11, lineHeight: 1 }}>&#x2192;</span>
      )}
    </button>
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
    <div className="flex flex-col gap-1">
      {/* Upstream badges */}
      {hasUp && (
        <div className="flex flex-wrap gap-1 items-center">
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
        <div className="flex flex-wrap gap-1 items-center">
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

/** Approximate monospace ch-width for the column name, capped at 30ch */
const MAX_NAME_CH = 30
const MIN_NAME_CH = 12
const CH_PX = 7.2 // approximate px per monospace character at text-xs

export function ColumnTable({ columns, columnLineage, columnDownstream }: ColumnTableProps) {
  const [expandedCol, setExpandedCol] = useState<string | null>(null)
  const hasAnyProfile = columns.some(c => c.profile != null)
  const hasAnyLineage = (columnLineage != null && Object.keys(columnLineage).length > 0)
    || (columnDownstream != null && Object.keys(columnDownstream).length > 0)

  // Compute a consistent name column width based on the longest name (capped)
  const nameColWidth = useMemo(() => {
    if (columns.length === 0) return MIN_NAME_CH * CH_PX
    const longest = Math.max(...columns.map(c => c.name.length))
    const chars = Math.min(Math.max(longest, MIN_NAME_CH), MAX_NAME_CH)
    // +4 for the expand chevron space, +32 for padding
    return chars * CH_PX + 4 + 32
  }, [columns])

  const totalCols = 4
    + (hasAnyProfile ? 2 : 0)
    + (hasAnyLineage ? 1 : 0)

  if (columns.length === 0) {
    return <div className="text-sm text-[var(--text-muted)]">No columns found.</div>
  }

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="w-full text-sm table-fixed">
        <colgroup>
          <col style={{ width: nameColWidth }} />
          <col style={{ width: 160 }} />
          <col />
          {hasAnyLineage && <col style={{ width: 320 }} />}
          {hasAnyProfile && (
            <>
              <col style={{ width: 120 }} />
              <col style={{ width: 80 }} />
            </>
          )}
          <col style={{ width: 100 }} />
        </colgroup>
        <thead className="bg-[var(--bg-surface)]">
          <tr>
            <th className="text-left px-4 py-2 font-medium">Column</th>
            <th className="text-left px-4 py-2 font-medium">Type</th>
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
            <th className="text-left px-4 py-2 font-medium">Tests</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => {
            const isExpanded = expandedCol === col.name
            const canExpand = col.profile != null
            const upDeps = columnLineage?.[col.name]
            const downDeps = columnDownstream?.[col.name]
            return (
              <tr key={col.name} id={`col-${col.name}`} className="group">
                <td colSpan={totalCols} className="p-0">
                  <div
                    className={`flex items-center border-t border-[var(--border)]
                      ${canExpand ? 'cursor-pointer hover:bg-[var(--bg-surface)]' : ''}
                      ${isExpanded ? 'bg-[var(--bg-surface)]' : ''}`}
                    onClick={() => canExpand && setExpandedCol(isExpanded ? null : col.name)}
                  >
                    {/* Column name */}
                    <div
                      className="px-4 py-2 font-mono text-xs font-medium shrink-0 flex items-start min-w-0"
                      style={{ width: nameColWidth }}
                    >
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
                      <div>
                        <span style={{ wordBreak: 'break-all' }}>
                          {col.name}
                        </span>
                        {col.insights?.role && (
                          <div className="mt-0.5">
                            <RoleBadge role={col.insights.role} confidence={col.insights.confidence} />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Type + semantic type */}
                    <div
                      className="px-4 py-2 font-mono text-xs text-[var(--text-muted)] uppercase shrink-0"
                      style={{ width: 160 }}
                    >
                      <div>{col.data_type || '—'}</div>
                      {col.insights?.semantic_type && (
                        <div className="text-[9px] normal-case opacity-60 mt-0.5">
                          {col.insights.semantic_type}
                        </div>
                      )}
                    </div>

                    {/* Description + insights */}
                    <div className="px-4 py-2 flex-1 min-w-0">
                      {col.description ? (
                        <span className="text-sm block">
                          {col.description}
                          {col.insights?.generated_description && col.description === col.insights.generated_description && (
                            <span className="ml-1.5 text-[9px] text-[var(--text-muted)] opacity-60 font-medium uppercase">auto</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-sm text-[var(--text-muted)] italic">No description</span>
                      )}
                      {col.insights?.sql_usage && col.insights.sql_usage.length > 0 && !col.insights.sql_usage.every(u => u === 'selected_only') && (
                        <div className="flex gap-1 mt-0.5">
                          {col.insights.sql_usage.filter(u => u !== 'selected_only').map(usage => (
                            <span key={usage} className="text-[9px] text-[var(--text-muted)] opacity-70">
                              {usage.replace('_', ' ')}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Unified lineage cell */}
                    {hasAnyLineage && (
                      <div className="px-4 py-1.5 shrink-0" style={{ width: 320 }}>
                        <LineageCell upstream={upDeps} downstream={downDeps} />
                      </div>
                    )}

                    {hasAnyProfile && (
                      <>
                        <div className="px-4 py-2 shrink-0" style={{ width: 120 }}>
                          {col.profile ? (
                            <NullBar rate={col.profile.null_rate} />
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </div>
                        <div className="px-4 py-2 text-right shrink-0" style={{ width: 80 }}>
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
                        </div>
                      </>
                    )}

                    <div className="px-4 py-2 shrink-0" style={{ width: 100 }}>
                      {col.tests.length > 0 ? (
                        <div className="flex gap-1 flex-wrap">
                          {col.tests.map((test, i) => (
                            <TestBadge key={i} status={test.status} label={test.test_type} />
                          ))}
                        </div>
                      ) : (
                        <span className="text-[var(--text-muted)]">—</span>
                      )}
                    </div>
                  </div>
                  {isExpanded && col.profile && (
                    <ProfileDetail profile={col.profile} />
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
