import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { buildProjectMap, nodesInLayer } from '../../utils/projectMap'
import { buildResourcePath } from '../../utils/resourceRoutes'
import type { DocglowData } from '../../types'

const DRILLDOWN_LIMIT = 60

/**
 * Sources → staging → … → exposures, with counts.
 *
 * Renders nothing when the project has fewer than two populated layers — a
 * single box is not a flow, and a small or flat project is better served by
 * search and the starting points below it.
 */
export function ProjectMap({ data }: { data: DocglowData }) {
  const navigate = useNavigate()
  const [openRank, setOpenRank] = useState<number | null>(null)

  const segments = useMemo(() => buildProjectMap(data), [data])
  const drilldown = useMemo(
    () => (openRank == null ? [] : nodesInLayer(data, openRank)),
    [data, openRank],
  )

  if (segments.length === 0) return null

  const openSegment = segments.find(s => s.rank === openRank)

  return (
    <section className="mb-8" aria-labelledby="project-map-heading">
      <h2
        id="project-map-heading"
        className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3"
      >
        Project map
      </h2>

      <div className="flex flex-wrap items-stretch gap-1">
        {segments.map((segment, i) => (
          <div key={segment.rank} className="flex items-stretch gap-1">
            {i > 0 && (
              <span
                aria-hidden="true"
                className="self-center text-[var(--text-muted)] text-sm select-none"
              >
                →
              </span>
            )}
            <button
              onClick={() => setOpenRank(openRank === segment.rank ? null : segment.rank)}
              aria-expanded={openRank === segment.rank}
              className={`px-3 py-2 rounded-lg border text-left transition-colors cursor-pointer
                          hover:border-primary/50 ${
                            openRank === segment.rank
                              ? 'border-primary'
                              : 'border-[var(--border)]'
                          }`}
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: segment.color }}
                />
                <span className="text-sm font-medium">{segment.label}</span>
              </span>
              <span className="block text-xs text-[var(--text-muted)] mt-0.5">
                {segment.count} {segment.count === 1 ? 'node' : 'nodes'}
              </span>
            </button>
          </div>
        ))}
      </div>

      {openSegment && (
        <div className="mt-3 p-3 border border-[var(--border)] rounded-lg bg-[var(--bg-surface)]">
          <p className="text-xs text-[var(--text-muted)] mb-2">
            {openSegment.label}
            {drilldown.length > DRILLDOWN_LIMIT && ` — showing ${DRILLDOWN_LIMIT} of ${drilldown.length}`}
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {drilldown.slice(0, DRILLDOWN_LIMIT).map(node => (
              <li key={node.id}>
                <button
                  onClick={() => navigate(buildResourcePath(node.id))}
                  className="px-2 py-1 text-xs rounded border border-[var(--border)]
                             hover:border-primary/50 hover:text-primary cursor-pointer transition-colors"
                >
                  {node.name}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
