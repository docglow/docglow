import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Markdown } from '../components/Markdown'
import { LineageFlow } from '../components/lineage/LineageFlow'
import { ColumnTraceDrawer } from '../components/models/ColumnTraceDrawer'
import { useProjectStore } from '../stores/projectStore'
import { getSubgraph } from '../utils/graph'
import { buildModelColumnsMap } from '../utils/modelColumns'
import { buildResourcePath } from '../utils/resourceRoutes'
import type { MetricDefinition, MetricInputRef } from '../types'

function inputLabel(input: MetricInputRef): string {
  const parts = [input.name]
  if (input.alias) parts.push(`as ${input.alias}`)
  if (input.offset) parts.push(`offset ${input.offset}`)
  return parts.join(' ')
}

/** One row per populated part of the definition, as label → code-ish value. */
function definitionRows(definition: MetricDefinition): [string, string][] {
  const rows: [string, string][] = []
  const { measure } = definition
  if (measure) {
    const expr = measure.expr && measure.expr !== measure.name ? measure.expr : undefined
    const aggregation = measure.agg ? `${measure.agg}(${expr ?? measure.name ?? ''})` : expr
    if (measure.name) rows.push(['Measure', measure.name])
    if (aggregation) rows.push(['Aggregation', aggregation])
    for (const filter of measure.filter ?? []) rows.push(['Measure filter', filter.trim()])
  }
  if (definition.numerator) rows.push(['Numerator', inputLabel(definition.numerator)])
  if (definition.denominator) rows.push(['Denominator', inputLabel(definition.denominator)])
  for (const input of definition.metrics ?? []) rows.push(['Input', inputLabel(input)])
  if (definition.expr) rows.push(['Expression', definition.expr])
  if (definition.window) rows.push(['Window', definition.window])
  if (definition.grain_to_date) rows.push(['Grain to date', definition.grain_to_date])
  const { conversion } = definition
  if (conversion) {
    if (conversion.base_measure) rows.push(['Base measure', conversion.base_measure])
    if (conversion.conversion_measure) rows.push(['Conversion measure', conversion.conversion_measure])
    if (conversion.entity) rows.push(['Entity', conversion.entity])
    if (conversion.calculation) rows.push(['Calculation', conversion.calculation])
    if (conversion.window) rows.push(['Window', conversion.window])
  }
  for (const filter of definition.filter ?? []) rows.push(['Filter', filter.trim()])
  return rows
}

export function MetricPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data, getMetric, getResource } = useProjectStore()

  const decodedId = id ? decodeURIComponent(id) : ''
  const metric = decodedId ? getMetric(decodedId) : undefined

  // Metrics sit at the end of the DAG, but derived metrics and exposures can
  // build on them, so show both directions.
  const [depth, setDepth] = useState(2)
  const [lineageFullscreen, setLineageFullscreen] = useState(false)
  const [traceOpen, setTraceOpen] = useState(false)

  const lineageSubgraph = useMemo(() => {
    if (!data?.lineage || !decodedId) return null

    const { nodes, edges } = getSubgraph(
      decodedId,
      data.lineage.nodes,
      data.lineage.edges,
      depth,
      'both',
    )

    if (nodes.length === 0) return null

    return {
      nodes,
      edges,
      layer_config: data.lineage.layer_config,
    }
  }, [data?.lineage, decodedId, depth])

  const modelColumns = useMemo(() => {
    if (!data) return {}
    return buildModelColumnsMap(data)
  }, [data])

  if (!metric) {
    return (
      <div className="text-[var(--text-muted)]">
        Metric not found: {id ? decodeURIComponent(id) : 'unknown'}
      </div>
    )
  }

  const title = metric.label?.trim() || metric.name
  const rows = metric.definition ? definitionRows(metric.definition) : []
  // Models and input metrics, linked when this site has a page for them.
  const builtOn = [...(metric.models ?? []), ...(metric.input_metrics ?? [])]

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-3 flex-wrap min-w-0 mb-2">
          <h1 className="text-2xl font-bold">{title}</h1>
          <span className="px-2 py-0.5 text-xs font-medium rounded bg-secondary/10 text-secondary">
            Metric
          </span>
          {metric.type && (
            <span className="px-2 py-0.5 text-xs font-medium rounded bg-neutral/10 text-neutral capitalize">
              {metric.type}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-4 text-sm text-[var(--text-muted)]">
          {title !== metric.name && <span className="font-mono">{metric.name}</span>}
          {(metric.semantic_models ?? []).length > 0 && (
            <span>Semantic model: {metric.semantic_models!.join(', ')}</span>
          )}
        </div>
        {metric.description && (
          <Markdown content={metric.description} className="mt-3 text-sm" />
        )}
      </div>

      {rows.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Definition</h2>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] p-4 text-sm">
            {rows.map(([label, value], i) => (
              <div key={`${label}-${i}`} className="contents">
                <dt className="text-[var(--text-muted)]">{label}</dt>
                <dd className="font-mono break-all whitespace-pre-wrap">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {builtOn.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Built on</h2>
          <div className="flex flex-wrap gap-2">
            {builtOn.map((uid) => {
              const resource = getResource(uid)
              const name = resource?.name ?? uid.split('.').pop()
              return resource ? (
                <button
                  key={uid}
                  onClick={() => navigate(buildResourcePath(uid))}
                  title={uid}
                  className="px-2 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-surface)]
                             hover:border-[var(--primary)] cursor-pointer transition-colors font-mono"
                >
                  {name}
                </button>
              ) : (
                <span
                  key={uid}
                  title={`${uid} (not in this site)`}
                  className="px-2 py-1 text-xs rounded border border-[var(--border)] text-[var(--text-muted)] font-mono"
                >
                  {name}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {((metric.columns ?? []).length > 0 || data?.column_lineage?.[metric.unique_id]) && (
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-lg font-semibold">Reads columns</h2>
            {data?.column_lineage?.[metric.unique_id] && (
              <button
                onClick={() => setTraceOpen(true)}
                className="px-2 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-surface)]
                           hover:border-[var(--primary)] cursor-pointer transition-colors"
              >
                Trace column lineage
              </button>
            )}
          </div>
          {(metric.columns ?? []).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {metric.columns!.map((ref) => {
                const model = getResource(ref.model)
                const label = `${model?.name ?? ref.model.split('.').pop()}.${ref.column}`
                return model ? (
                  <button
                    key={`${ref.model}.${ref.column}`}
                    onClick={() => navigate(buildResourcePath(ref.model, `#col-${ref.column.toLowerCase()}`))}
                    title={`${ref.model} · ${ref.column}`}
                    className="px-2 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-surface)]
                               hover:border-[var(--primary)] cursor-pointer transition-colors font-mono"
                  >
                    {label}
                  </button>
                ) : (
                  <span
                    key={`${ref.model}.${ref.column}`}
                    title={`${ref.model} (not in this site)`}
                    className="px-2 py-1 text-xs rounded border border-[var(--border)] text-[var(--text-muted)] font-mono"
                  >
                    {label}
                  </span>
                )
              })}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              Through its input metrics. Trace the lineage to see the columns behind them.
            </p>
          )}
        </div>
      )}

      {traceOpen && data?.column_lineage && (
        <ColumnTraceDrawer
          modelId={metric.unique_id}
          columnName={metric.name}
          columnLineageData={data.column_lineage}
          onClose={() => setTraceOpen(false)}
        />
      )}

      {metric.tags.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Tags</h2>
          <div className="flex flex-wrap gap-2">
            {metric.tags.map((tag) => (
              <span
                key={tag}
                className="px-2 py-1 text-xs rounded-full border border-[var(--border)] bg-[var(--bg-surface)]"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className={lineageFullscreen ? 'fixed inset-0 z-50 bg-[var(--bg)] flex flex-col p-4' : ''}>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2 shrink-0">
          <h2 className="text-lg font-semibold">Lineage Context</h2>
          {lineageSubgraph && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--text-muted)]">Depth</label>
              <input
                type="range"
                min={1}
                max={6}
                value={depth}
                onChange={(e) => setDepth(Number(e.target.value))}
                className="w-20 accent-[var(--primary)]"
              />
              <span className="text-xs font-medium w-4 text-center">{depth}</span>
              <span className="text-xs text-[var(--text-muted)] ml-2">
                {lineageSubgraph.nodes.length} nodes · {lineageSubgraph.edges.length} edges
              </span>
              <div className="h-4 w-px bg-[var(--border)]" />
              <button
                onClick={() => setLineageFullscreen((f) => !f)}
                className="p-1 rounded hover:bg-[var(--bg-surface)] cursor-pointer transition-colors text-[var(--text-muted)] hover:text-[var(--text)]"
                title={lineageFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
              >
                {lineageFullscreen ? (
                  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M8 3v3a2 2 0 01-2 2H3M21 8h-3a2 2 0 01-2-2V3M3 16h3a2 2 0 012 2v3M16 21v-3a2 2 0 012-2h3" />
                  </svg>
                ) : (
                  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                  </svg>
                )}
              </button>
            </div>
          )}
        </div>
        {lineageSubgraph ? (
          <div
            className={lineageFullscreen ? 'flex-1 relative min-h-0' : 'relative'}
            style={lineageFullscreen ? undefined : { height: 'calc(100vh - 360px)', minHeight: 400 }}
          >
            <LineageFlow
              nodes={lineageSubgraph.nodes}
              edges={lineageSubgraph.edges}
              pinnedIds={new Set([decodedId])}
              layerConfig={lineageSubgraph.layer_config}
              modelColumns={modelColumns}
              onNavigateAway={() => setLineageFullscreen(false)}
            />
          </div>
        ) : (
          <div className="border border-[var(--border)] rounded-lg p-4 text-sm text-[var(--text-muted)]">
            No lineage context is available for this metric.
          </div>
        )}
      </div>
    </div>
  )
}
