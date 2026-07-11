import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ResponsiveTable } from '../components/ui/ResponsiveTable'
import { useProjectStore } from '../stores/projectStore'
import { formatPercent } from '../utils/formatting'
import type { CoverageMetric } from '../types'

type Tab = 'overview' | 'documentation' | 'testing' | 'complexity' | 'naming' | 'orphans'

function gradeColor(grade: string): string {
  switch (grade) {
    case 'A': return 'text-success'
    case 'B': return 'text-primary'
    case 'C': return 'text-warning'
    case 'D':
    case 'F': return 'text-danger'
    default: return 'text-[var(--text-muted)]'
  }
}

function scoreBarColor(score: number): string {
  if (score >= 80) return 'bg-success'
  if (score >= 60) return 'bg-warning'
  return 'bg-danger'
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm w-36 shrink-0">{label}</span>
      <div className="flex-1 h-2.5 bg-[var(--bg-surface)] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${scoreBarColor(score)}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className="text-sm font-medium w-10 text-right">{score.toFixed(0)}</span>
    </div>
  )
}

function CoverageBar({ metric, label }: { metric: CoverageMetric; label: string }) {
  const value = `${metric.covered}/${metric.total} (${formatPercent(metric.rate)})`

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_8.5rem] gap-x-4 gap-y-2 sm:grid-cols-[minmax(10rem,18rem)_minmax(8rem,1fr)_8.5rem] sm:items-center">
      <span className="text-sm text-[var(--text-muted)] truncate" title={label}>
        {label}
      </span>
      <span className="text-xs text-right text-[var(--text-muted)] whitespace-nowrap tabular-nums sm:col-start-3">
        {value}
      </span>
      <div className="col-span-2 h-2 bg-[var(--bg-surface)] rounded-full overflow-hidden sm:col-span-1 sm:col-start-2 sm:row-start-1">
        <div
          className={`h-full rounded-full ${scoreBarColor(metric.rate * 100)}`}
          style={{ width: `${metric.rate * 100}%` }}
        />
      </div>
    </div>
  )
}

export function HealthPage() {
  const { data } = useProjectStore()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')

  if (!data) return null

  const health = data.health
  const score = health.score
  const coverage = health.coverage

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'documentation', label: 'Documentation' },
    { key: 'testing', label: 'Testing' },
    { key: 'complexity', label: 'Complexity' },
    { key: 'naming', label: 'Naming' },
    { key: 'orphans', label: `Orphans (${health.orphans.length})` },
  ]

  return (
    <div className="w-full max-w-none">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">Project Health</h1>
        <div className="flex items-center gap-6">
          <div className="flex items-baseline gap-2">
            <span className={`text-5xl font-bold ${gradeColor(score.grade)}`}>
              {score.grade}
            </span>
            <span className="text-2xl text-[var(--text-muted)]">
              {score.overall.toFixed(0)}/100
            </span>
          </div>
          <div className="flex-1 space-y-1.5">
            <ScoreBar label="Documentation" score={score.documentation} />
            <ScoreBar label="Testing" score={score.testing} />
            <ScoreBar label="Freshness" score={score.freshness} />
            <ScoreBar label="Complexity" score={score.complexity} />
            <ScoreBar label="Naming" score={score.naming} />
            <ScoreBar label="Orphan Detection" score={score.orphans} />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-[var(--border)] flex gap-0 mb-4">
        {tabs.map(t => (
          <button key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer
                    ${tab === t.key
                      ? 'border-primary text-primary'
                      : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]'
                    }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && (
        <div className="grid grid-cols-2 gap-4">
          <StatCard title="Models Documented" metric={coverage.models_documented} />
          <StatCard title="Columns Documented" metric={coverage.columns_documented} />
          <StatCard title="Models Tested" metric={coverage.models_tested} />
          <StatCard title="Columns Tested" metric={coverage.columns_tested} />
          <div className="border border-[var(--border)] rounded-lg p-4 bg-[var(--bg-surface)]">
            <div className="text-sm text-[var(--text-muted)] mb-1">High Complexity</div>
            <div className="text-2xl font-bold">{health.complexity.high_count}</div>
            <div className="text-xs text-[var(--text-muted)]">of {health.complexity.total} models</div>
          </div>
          <div className="border border-[var(--border)] rounded-lg p-4 bg-[var(--bg-surface)]">
            <div className="text-sm text-[var(--text-muted)] mb-1">Naming Violations</div>
            <div className="text-2xl font-bold">{health.naming.violations.length}</div>
            <div className="text-xs text-[var(--text-muted)]">
              {health.naming.compliant_count}/{health.naming.total_checked} compliant
            </div>
          </div>
        </div>
      )}

      {tab === 'documentation' && (
        <div className="space-y-6">
          <div className="space-y-2">
            <h3 className="font-medium">Coverage by Folder</h3>
            {Object.entries(coverage.by_folder)
              .sort(([, a], [, b]) => a.rate - b.rate)
              .map(([folder, metric]) => (
                <CoverageBar key={folder} label={folder || '(root)'} metric={metric} />
              ))}
          </div>
          {coverage.undocumented_models.length > 0 && (
            <div>
              <h3 className="font-medium mb-2">
                Undocumented Models ({coverage.undocumented_models.length})
              </h3>
              <ModelTable
                models={coverage.undocumented_models}
                extraColumn="Downstream"
                extraValue={m => String(m.downstream_count)}
                onNavigate={uid => navigate(`/model/${encodeURIComponent(uid)}`)}
              />
            </div>
          )}
        </div>
      )}

      {tab === 'testing' && (
        <div className="space-y-6">
          <div className="space-y-2">
            <CoverageBar label="Models with tests" metric={coverage.models_tested} />
            <CoverageBar label="Columns with tests" metric={coverage.columns_tested} />
          </div>
          {coverage.untested_models.length > 0 && (
            <div>
              <h3 className="font-medium mb-2">
                Untested Models ({coverage.untested_models.length})
              </h3>
              <ModelTable
                models={coverage.untested_models}
                extraColumn="Downstream"
                extraValue={m => String(m.downstream_count)}
                onNavigate={uid => navigate(`/model/${encodeURIComponent(uid)}`)}
              />
            </div>
          )}
        </div>
      )}

      {tab === 'complexity' && (
        <div>
          {health.complexity.models.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">No high-complexity models found.</p>
          ) : (
            <ResponsiveTable defaultMinWidth={1040}>
              <colgroup>
                <col />
                <col className="w-24" />
                <col className="w-20" />
                <col className="w-20" />
                <col className="w-28" />
                <col className="w-28" />
              </colgroup>
              <thead className="bg-[var(--bg-surface)]">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Model</th>
                  <th className="text-right px-4 py-2 font-medium whitespace-nowrap">SQL Lines</th>
                  <th className="text-right px-4 py-2 font-medium whitespace-nowrap">Joins</th>
                  <th className="text-right px-4 py-2 font-medium whitespace-nowrap">CTEs</th>
                  <th className="text-right px-4 py-2 font-medium whitespace-nowrap">Subqueries</th>
                  <th className="text-right px-4 py-2 font-medium whitespace-nowrap">Downstream</th>
                </tr>
              </thead>
              <tbody>
                {health.complexity.models.map(m => (
                  <tr key={m.unique_id}
                      className="border-t border-[var(--border)] hover:bg-[var(--bg-surface)] cursor-pointer"
                      onClick={() => navigate(`/model/${encodeURIComponent(m.unique_id)}`)}>
                    <td className="px-4 py-2">
                      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                        <span className="font-medium text-primary break-words" title={m.name}>
                          {m.name}
                        </span>
                        <span className="text-xs text-[var(--text-muted)] whitespace-nowrap" title={m.folder}>
                          {m.folder}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{m.sql_lines}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{m.join_count}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{m.cte_count}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{m.subquery_count}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{m.downstream_count}</td>
                  </tr>
                ))}
              </tbody>
            </ResponsiveTable>
          )}
        </div>
      )}

      {tab === 'naming' && (
        <div>
          {health.naming.violations.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">All models follow naming conventions.</p>
          ) : (
            <ResponsiveTable defaultMinWidth={760}>
              <thead className="bg-[var(--bg-surface)]">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Model</th>
                  <th className="text-left px-4 py-2 font-medium">Layer</th>
                  <th className="text-left px-4 py-2 font-medium">Expected Pattern</th>
                </tr>
              </thead>
              <tbody>
                {health.naming.violations.map(v => (
                  <tr key={v.unique_id}
                      className="border-t border-[var(--border)] hover:bg-[var(--bg-surface)] cursor-pointer"
                      onClick={() => navigate(`/model/${encodeURIComponent(v.unique_id)}`)}>
                    <td className="px-4 py-2">
                      <span className="font-medium text-primary">{v.name}</span>
                      <span className="text-xs text-[var(--text-muted)] ml-2">{v.folder}</span>
                    </td>
                    <td className="px-4 py-2 capitalize">{v.layer}</td>
                    <td className="px-4 py-2 font-mono text-xs">{v.expected_pattern}</td>
                  </tr>
                ))}
              </tbody>
            </ResponsiveTable>
          )}
        </div>
      )}

      {tab === 'orphans' && (
        <div>
          {health.orphans.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">No orphan models found.</p>
          ) : (
            <>
              <p className="text-sm text-[var(--text-muted)] mb-3">
                Models with no downstream consumers.
              </p>
              <ModelTable
                models={health.orphans.map(o => ({ ...o, downstream_count: 0 }))}
                onNavigate={uid => navigate(`/model/${encodeURIComponent(uid)}`)}
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}

function StatCard({ title, metric }: { title: string; metric: CoverageMetric }) {
  return (
    <div className="border border-[var(--border)] rounded-lg p-4 bg-[var(--bg-surface)]">
      <div className="text-sm text-[var(--text-muted)] mb-1">{title}</div>
      <div className="text-2xl font-bold">{formatPercent(metric.rate)}</div>
      <div className="text-xs text-[var(--text-muted)]">
        {metric.covered} / {metric.total}
      </div>
      <div className="mt-2 h-1.5 bg-[var(--bg)] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${scoreBarColor(metric.rate * 100)}`}
          style={{ width: `${metric.rate * 100}%` }}
        />
      </div>
    </div>
  )
}

function ModelTable({
  models,
  extraColumn,
  extraValue,
  onNavigate,
}: {
  models: { unique_id: string; name: string; folder: string; downstream_count?: number }[]
  extraColumn?: string
  extraValue?: (m: { downstream_count?: number }) => string
  onNavigate: (uid: string) => void
}) {
  return (
    <ResponsiveTable defaultMinWidth={760}>
      <colgroup>
        <col />
        <col className="w-72" />
        {extraColumn && <col className="w-32" />}
      </colgroup>
      <thead className="bg-[var(--bg-surface)]">
        <tr>
          <th className="text-left px-4 py-2 font-medium">Model</th>
          <th className="text-left px-4 py-2 font-medium">Folder</th>
          {extraColumn && (
            <th className="text-right px-4 py-2 font-medium">{extraColumn}</th>
          )}
        </tr>
      </thead>
      <tbody>
        {models.map(m => (
          <tr key={m.unique_id}
              className="border-t border-[var(--border)] hover:bg-[var(--bg-surface)] cursor-pointer"
              onClick={() => onNavigate(m.unique_id)}>
            <td className="px-4 py-2">
              <div className="font-medium text-primary break-words" title={m.name}>
                {m.name}
              </div>
            </td>
            <td className="px-4 py-2 text-[var(--text-muted)]">
              <div className="truncate" title={m.folder || '—'}>
                {m.folder || '—'}
              </div>
            </td>
            {extraColumn && extraValue && (
              <td className="px-4 py-2 text-right tabular-nums">{extraValue(m)}</td>
            )}
          </tr>
        ))}
      </tbody>
    </ResponsiveTable>
  )
}
