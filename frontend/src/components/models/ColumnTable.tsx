import { useState } from 'react'
import type { DocglowColumn, ColumnProfile, TopValue, HistogramBin } from '../../types'
import { TestBadge } from '../tests/TestBadge'
import { formatNumber, formatPercent } from '../../utils/formatting'

interface ColumnTableProps {
  columns: DocglowColumn[]
}

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

export function ColumnTable({ columns }: ColumnTableProps) {
  const [expandedCol, setExpandedCol] = useState<string | null>(null)
  const hasAnyProfile = columns.some(c => c.profile != null)

  if (columns.length === 0) {
    return <div className="text-sm text-[var(--text-muted)]">No columns found.</div>
  }

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg-surface)]">
          <tr>
            <th className="text-left px-4 py-2 font-medium">Column</th>
            <th className="text-left px-4 py-2 font-medium">Type</th>
            <th className="text-left px-4 py-2 font-medium">Description</th>
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
            return (
              <tr key={col.name} className="group">
                <td colSpan={hasAnyProfile ? 6 : 4} className="p-0">
                  <div
                    className={`flex items-center border-t border-[var(--border)]
                      ${canExpand ? 'cursor-pointer hover:bg-[var(--bg-surface)]' : ''}
                      ${isExpanded ? 'bg-[var(--bg-surface)]' : ''}`}
                    onClick={() => canExpand && setExpandedCol(isExpanded ? null : col.name)}
                  >
                    <div className="px-4 py-2 font-mono text-xs font-medium min-w-[160px]">
                      {canExpand && (
                        <svg
                          className={`w-3 h-3 inline-block mr-1 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                          fill="currentColor" viewBox="0 0 20 20"
                        >
                          <path fillRule="evenodd"
                                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                                clipRule="evenodd" />
                        </svg>
                      )}
                      {col.name}
                    </div>
                    <div className="px-4 py-2 font-mono text-xs text-[var(--text-muted)] min-w-[100px]">
                      {col.data_type || '—'}
                    </div>
                    <div className="px-4 py-2 flex-1 min-w-0">
                      {col.description ? (
                        <span className="text-sm truncate block">{col.description}</span>
                      ) : (
                        <span className="text-sm text-[var(--text-muted)] italic">No description</span>
                      )}
                    </div>
                    {hasAnyProfile && (
                      <>
                        <div className="px-4 py-2 min-w-[120px]">
                          {col.profile ? (
                            <NullBar rate={col.profile.null_rate} />
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </div>
                        <div className="px-4 py-2 text-right min-w-[80px]">
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
                    <div className="px-4 py-2 min-w-[100px]">
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
