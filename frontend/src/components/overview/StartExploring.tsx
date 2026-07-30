import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { computeSuggestions } from '../../utils/lineageSuggestions'
import type { DocglowData } from '../../types'

// Eight fills the four-column layout evenly on a desktop viewport, and still
// splits cleanly at two columns.
const CARD_COUNT = 8

/**
 * The same connectivity-ranked entry points the Lineage Explorer offers, lifted
 * onto the landing page. Clicking one opens the graph already pinned to it, so
 * the first thing a reader sees of lineage is a readable neighbourhood rather
 * than the whole DAG.
 */
export function StartExploring({ data }: { data: DocglowData }) {
  const navigate = useNavigate()

  const suggestions = useMemo(
    () => computeSuggestions(data.lineage.nodes, data.lineage.edges, CARD_COUNT),
    [data],
  )

  if (suggestions.length === 0) return null

  return (
    <section className="mb-8" aria-labelledby="start-exploring-heading">
      <h2
        id="start-exploring-heading"
        className="text-sm font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-1"
      >
        Start exploring
      </h2>
      <p className="text-xs text-[var(--text-muted)] mb-3">
        The most connected models in your project. Click a model to explore.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {suggestions.map(s => (
          <button
            key={s.node.id}
            onClick={() => navigate(`/lineage?pins=${encodeURIComponent(s.node.id)}`)}
            className="text-left p-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)]
                       hover:border-primary/50 cursor-pointer transition-colors group"
          >
            <div className="font-medium text-sm group-hover:text-primary transition-colors truncate">
              {s.node.name}
            </div>
            <div className="text-xs text-[var(--text-muted)] truncate mt-0.5">{s.node.folder}</div>
            <div className="flex gap-3 mt-2 text-xs text-[var(--text-muted)]">
              <span>{s.upstreamCount} upstream</span>
              <span>{s.downstreamCount} downstream</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}
