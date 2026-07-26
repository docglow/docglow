import { useMemo } from 'react'
import { useProjectStore } from '../stores/projectStore'
import { useTagFilterStore } from '../stores/tagFilterStore'
import { formatNumber } from '../utils/formatting'
import { ProjectSearch } from '../components/overview/ProjectSearch'
import { ProjectMap } from '../components/overview/ProjectMap'
import { StartExploring } from '../components/overview/StartExploring'
import { HealthStrip } from '../components/overview/HealthStrip'
import type { DocglowModel } from '../types'

function FilteredModels({ models, total }: { models: DocglowModel[]; total: number }) {
  return (
    <section className="mb-8" aria-labelledby="filtered-models-heading">
      <div className="flex items-baseline gap-2 mb-3">
        <h2 id="filtered-models-heading" className="text-lg font-semibold">Filtered Models</h2>
        <span className="text-xs text-[var(--text-muted)]">
          {models.length} of {total}
        </span>
      </div>
      {models.length === 0 ? (
        <p className="px-4 py-3 text-sm text-[var(--text-muted)] border border-[var(--border)] rounded-lg">
          No models carry the selected tags. Tags may still be set on sources or exposures.
        </p>
      ) : (
      <div className="border border-[var(--border)] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-surface)]">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Model</th>
              <th className="text-left px-4 py-2 font-medium">Materialization</th>
              <th className="text-left px-4 py-2 font-medium">Columns</th>
              <th className="text-left px-4 py-2 font-medium">Tests</th>
            </tr>
          </thead>
          <tbody>
            {models.slice(0, 10).map(model => {
              const passing = model.test_results.filter(t => t.status === 'pass').length
              const total = model.test_results.length
              return (
                <tr key={model.unique_id}
                    className="border-t border-[var(--border)] hover:bg-[var(--bg-surface)] cursor-pointer"
                    onClick={() => window.location.hash = `#/model/${encodeURIComponent(model.unique_id)}`}>
                  <td className="px-4 py-2">
                    <span className="font-medium text-primary">{model.name}</span>
                    {model.description && (
                      <p className="text-xs text-[var(--text-muted)] truncate max-w-xs">
                        {model.description}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2 capitalize">{model.materialization}</td>
                  <td className="px-4 py-2">{model.columns.length}</td>
                  <td className="px-4 py-2">
                    {total > 0 ? (
                      <span className={passing === total ? 'text-success' : 'text-warning'}>
                        {passing}/{total}
                      </span>
                    ) : (
                      <span className="text-[var(--text-muted)]">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      )}
    </section>
  )
}

export function Overview() {
  const { data } = useProjectStore()
  const { selected: tagSelected, mode: tagMode } = useTagFilterStore()

  const filteredModels = useMemo(() => {
    if (!data || tagSelected.size === 0) return []
    return Object.values(data.models).filter(m => {
      const hasMatch = m.tags.some(t => tagSelected.has(t))
      return tagMode === 'include' ? hasMatch : !hasMatch
    })
  }, [data, tagSelected, tagMode])

  if (!data) return null

  const modelCount = Object.keys(data.models).length
  const sourceCount = Object.keys(data.sources).length
  const exposureCount = Object.keys(data.exposures).length
  const testCount = Object.values(data.models).reduce(
    (sum, m) => sum + m.test_results.length, 0
  )

  // Totals belong in a footnote, not four tiles above the fold. The counts are
  // context for what's on the page; they aren't what anyone came to find out.
  const totals = [
    `${formatNumber(modelCount)} models`,
    `${formatNumber(sourceCount)} sources`,
    `${formatNumber(testCount)} tests`,
    exposureCount > 0 ? `${formatNumber(exposureCount)} exposures` : null,
  ].filter(Boolean)

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-1">{data.metadata.project_name}</h1>
      <p className="text-[var(--text-muted)] text-sm mb-6">
        {totals.join(' · ')}
      </p>

      <ProjectSearch />
      <ProjectMap data={data} />
      <StartExploring data={data} />
      <HealthStrip health={data.health} />

      {/* Tag filters are set from the sidebar and apply site-wide, so the landing
          page still has to answer "what matched?". Unfiltered, this table used to
          render the first ten models in manifest order under the heading "Recent
          Models" — an ordering that never existed (DOC-297). */}
      {tagSelected.size > 0 && (
        <FilteredModels models={filteredModels} total={modelCount} />
      )}

      <p className="text-xs text-[var(--text-muted)]">
        Generated by docglow v{data.metadata.docglow_version}
        {' '}&middot; dbt v{data.metadata.dbt_version}
      </p>
    </div>
  )
}
