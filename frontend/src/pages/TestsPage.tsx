import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../stores/projectStore'
import { TestBadge } from '../components/tests/TestBadge'
import { TestSummaryTiles } from '../components/tests/TestSummaryTiles'
import { formatDuration, formatPercent, timeAgo } from '../utils/formatting'
import { EMPTY_FILTERS, filterTests, type TestFilters } from '../utils/testFilters'
import { testRowHasDetail } from '../utils/testStatus'
import type { ProjectTest, TestSeverity } from '../types'

function SeverityPill({ severity }: { severity: TestSeverity }) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide rounded ${
        severity === 'warn'
          ? 'bg-warning/10 text-warning'
          : 'bg-[var(--bg-surface)] text-[var(--text-muted)]'
      }`}
    >
      {severity}
    </span>
  )
}

function TestRow({ test }: { test: ProjectTest }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const hasDetail = testRowHasDetail(test)
  const primary = test.attached[0]

  return (
    <>
      <tr
        className={`border-t border-[var(--border)] ${hasDetail ? 'cursor-pointer hover:bg-[var(--bg-surface)]' : ''}`}
        onClick={hasDetail ? () => setOpen(o => !o) : undefined}
      >
        <td className="px-3 py-2">
          <TestBadge status={test.status} />
        </td>
        <td className="px-3 py-2 font-mono text-xs">{test.name}</td>
        <td className="px-3 py-2 whitespace-nowrap">{test.test_type}</td>
        <td className="px-3 py-2">
          {primary ? (
            <button
              onClick={e => {
                e.stopPropagation()
                if (primary.resource_type === 'source') navigate(`/source/${primary.unique_id}`)
                else navigate(`/model/${primary.unique_id}`)
              }}
              className="text-primary hover:underline cursor-pointer"
            >
              {primary.name}
            </button>
          ) : (
            <span className="text-[var(--text-muted)]">—</span>
          )}
          {test.attached.length > 1 && (
            <span className="text-[var(--text-muted)] text-xs"> +{test.attached.length - 1}</span>
          )}
        </td>
        <td className="px-3 py-2 text-[var(--text-muted)]">{test.column_name ?? '—'}</td>
        <td className="px-3 py-2">
          <SeverityPill severity={test.severity} />
        </td>
        <td className="px-3 py-2 text-right tabular-nums">
          {test.failures == null ? '—' : test.failures}
        </td>
        <td className="px-3 py-2 text-right text-[var(--text-muted)] whitespace-nowrap">
          {formatDuration(test.execution_time)}
        </td>
      </tr>
      {open && (
        <tr className="border-t border-[var(--border)] bg-[var(--bg-surface)]">
          <td colSpan={8} className="px-3 py-3">
            {test.message && (
              <div className="mb-2">
                <div className="text-xs font-medium text-[var(--text-muted)] mb-1">Message</div>
                <pre className="text-xs whitespace-pre-wrap font-mono text-danger">{test.message}</pre>
              </div>
            )}
            <div className="text-xs text-[var(--text-muted)]">
              Defined in <code className="font-mono">{test.original_file_path || 'unknown'}</code>
              {test.attached.length > 1 && (
                <> · validates {test.attached.map(a => a.name).join(', ')}</>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export function TestsPage() {
  const data = useProjectStore(s => s.data)
  const [filters, setFilters] = useState<TestFilters>(EMPTY_FILTERS)

  const testsData = data?.tests
  const filtered = useMemo(
    () => (testsData ? filterTests(testsData.tests, filters) : []),
    [testsData, filters],
  )

  if (!data) return null

  if (!testsData || testsData.tests.length === 0) {
    return (
      <div className="max-w-5xl">
        <h1 className="text-2xl font-bold mb-2">Tests</h1>
        <div className="border border-[var(--border)] rounded-lg p-6 text-sm text-[var(--text-muted)]">
          No tests are defined in this project. Add generic tests (e.g.{' '}
          <code className="font-mono">not_null</code>, <code className="font-mono">unique</code>) or
          singular tests to your dbt project to see them here.
        </div>
      </div>
    )
  }

  const summary = testsData.summary
  const set = (patch: Partial<TestFilters>) => setFilters(f => ({ ...f, ...patch }))

  return (
    <div className="max-w-5xl">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold mb-1">Tests</h1>
        <p className="text-sm text-[var(--text-muted)]">
          {summary.has_run_results ? (
            <>
              {summary.total} tests · pass rate {formatPercent(summary.pass_rate)} · last run{' '}
              {timeAgo(summary.generated_at)} · covers {summary.resources_tested} resources
            </>
          ) : (
            <>{summary.total} tests defined · covers {summary.resources_tested} resources</>
          )}
        </p>
      </div>

      {!summary.has_run_results && (
        <div className="mb-4 border border-warning/30 bg-warning/5 text-warning rounded-lg px-4 py-3 text-sm">
          No <code className="font-mono">run_results.json</code> was found, so tests are shown as{' '}
          <em>defined but not run</em>. Run <code className="font-mono">dbt test</code> or{' '}
          <code className="font-mono">dbt build</code> and regenerate to see pass/fail results.
        </div>
      )}

      <TestSummaryTiles
        summary={summary}
        activeStatus={filters.status}
        onSelectStatus={status => set({ status })}
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <input
          type="text"
          value={filters.query}
          onChange={e => set({ query: e.target.value })}
          placeholder="Search tests, columns, models…"
          className="px-3 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--bg)]
                     min-w-[220px] flex-1 focus:outline-none focus:border-primary"
        />
        <select
          value={filters.type}
          onChange={e => set({ type: e.target.value })}
          className="px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--bg)] cursor-pointer"
        >
          <option value="all">All types</option>
          {Object.entries(summary.by_type).map(([type, count]) => (
            <option key={type} value={type}>
              {type} ({count})
            </option>
          ))}
        </select>
        {(filters.status !== 'all' || filters.type !== 'all' || filters.query !== '') && (
          <button
            onClick={() => setFilters(EMPTY_FILTERS)}
            className="px-2 py-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text)] cursor-pointer"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="border border-[var(--border)] rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-surface)]">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-left px-3 py-2 font-medium">Test</th>
                <th className="text-left px-3 py-2 font-medium">Type</th>
                <th className="text-left px-3 py-2 font-medium">Resource</th>
                <th className="text-left px-3 py-2 font-medium">Column</th>
                <th className="text-left px-3 py-2 font-medium">Severity</th>
                <th className="text-right px-3 py-2 font-medium">Failures</th>
                <th className="text-right px-3 py-2 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(test => (
                <TestRow key={test.unique_id} test={test} />
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="p-4 text-sm text-[var(--text-muted)]">
            No tests match the current filters.
          </div>
        )}
      </div>

      {filtered.length > 0 && (
        <div className="mt-2 text-xs text-[var(--text-muted)]">
          Showing {filtered.length} of {summary.total} tests
        </div>
      )}
    </div>
  )
}
