#!/usr/bin/env node
/**
 * Benchmark search performance against a generated docglow-data.json.
 *
 * Usage:
 *   node scripts/bench_search.mjs path/to/docglow-data.json
 *   node scripts/bench_search.mjs path/to/docglow-data.json --queries "orders,user_id,stg_,payment"
 *
 * Generates the data file with:
 *   docglow generate --project-dir ~/analytics/dbt/point_analytics \
 *     --output-dir /tmp/bench-search --skip-column-lineage
 */

import { readFileSync } from 'fs'
import { createRequire } from 'module'
import { resolve } from 'path'
import { performance } from 'perf_hooks'

const require = createRequire(
  resolve(process.cwd(), 'frontend', 'node_modules', 'minisearch', 'package.json')
)
const MiniSearch = require('minisearch').default ?? require('minisearch')

// --- Parse args ---
const args = process.argv.slice(2)
const dataPath = args.find(a => !a.startsWith('--'))
const queriesIdx = args.indexOf('--queries')
const queriesArg = args.find(a => a.startsWith('--queries='))
  ?? (queriesIdx >= 0 ? args[queriesIdx + 1] : undefined)

if (!dataPath) {
  console.error('Usage: node scripts/bench_search.mjs <path-to-docglow-data.json> [--queries "q1,q2,q3"]')
  process.exit(1)
}

const defaultQueries = [
  'orders',        // common model name
  'user_id',       // common column name
  'stg_',          // prefix search
  'payment',       // partial match
  'description',   // field that appears in many models
  'fct_revenue',   // specific model
  'created_at',    // ubiquitous column
  'xyznotfound',   // no-match case
]

const queries = queriesArg
  ? queriesArg.replace('--queries=', '').split(',').map(q => q.trim())
  : defaultQueries

// --- Load data ---
console.log(`\nLoading ${dataPath}...`)
const raw = readFileSync(dataPath, 'utf-8')
const t0 = performance.now()
const data = JSON.parse(raw)
const tJson = performance.now()

const searchIndex = data.search_index
if (!searchIndex || !Array.isArray(searchIndex)) {
  console.error('No search_index array found in data file')
  process.exit(1)
}

// --- Analyze index ---
const resourceEntries = searchIndex.filter(e => e.resource_type !== 'column')
const columnEntries = searchIndex.filter(e => e.resource_type === 'column')
const indexJson = JSON.stringify(searchIndex)

console.log(`  File size:        ${(raw.length / 1024 / 1024).toFixed(1)} MB`)
console.log(`  JSON parse:       ${(tJson - t0).toFixed(0)}ms`)
console.log(`  Total entries:    ${searchIndex.length.toLocaleString()}`)
console.log(`  Resource entries: ${resourceEntries.length.toLocaleString()}`)
console.log(`  Column entries:   ${columnEntries.length.toLocaleString()}`)
console.log(`  Index JSON size:  ${(indexJson.length / 1024 / 1024).toFixed(1)} MB`)

const hasId = 'id' in (searchIndex[0] || {})
console.log(`  Has id field:     ${hasId}`)

if (!hasId) {
  console.error('\nError: search index entries need an "id" field for MiniSearch.')
  console.error('Regenerate with the latest docglow version.')
  process.exit(1)
}

// --- Benchmark: Two-tier MiniSearch (matching production implementation) ---
console.log(`\n--- MiniSearch: Two-Tier (resource + column) ---`)

const RESOURCE_THRESHOLD = 5
const MAX_RESULTS = 20

// Build resource index
const initTimes = []
let resIdx, colIdx
for (let i = 0; i < 3; i++) {
  const t1 = performance.now()
  resIdx = new MiniSearch({
    fields: ['name', 'description', 'tags'],
    storeFields: ['id', 'unique_id', 'name', 'resource_type', 'description', 'tags'],
    idField: 'id',
    searchOptions: { prefix: true, fuzzy: 0.2, boost: { name: 2 } },
  })
  resIdx.addAll(resourceEntries)

  colIdx = new MiniSearch({
    fields: ['name', 'description', 'model_name'],
    storeFields: ['id', 'unique_id', 'name', 'resource_type', 'column_name', 'model_name', 'description'],
    idField: 'id',
    searchOptions: { prefix: true, fuzzy: 0.2, boost: { name: 2 } },
  })
  colIdx.addAll(columnEntries)
  const t2 = performance.now()
  initTimes.push(t2 - t1)
}
initTimes.sort((a, b) => a - b)
console.log(`  Init times:       ${initTimes.map(t => t.toFixed(0) + 'ms').join(', ')}`)
console.log(`  Median init:      ${initTimes[1].toFixed(0)}ms`)

// Search queries
console.log(`\n  ${'Query'.padEnd(20)} ${'Results'.padStart(8)} ${'Time'.padStart(10)} ${'Avg (3 runs)'.padStart(14)}`)
console.log(`  ${'─'.repeat(20)} ${'─'.repeat(8)} ${'─'.repeat(10)} ${'─'.repeat(14)}`)

for (const query of queries) {
  const times = []
  let resultCount = 0
  for (let i = 0; i < 3; i++) {
    const t1 = performance.now()

    // Two-tier search (matches production logic)
    const resourceResults = resIdx.search(query, { limit: MAX_RESULTS })
    let results
    if (resourceResults.length < RESOURCE_THRESHOLD) {
      const remaining = MAX_RESULTS - resourceResults.length
      const columnResults = colIdx.search(query, { limit: remaining })
      results = [...resourceResults, ...columnResults]
    } else {
      results = resourceResults.slice(0, MAX_RESULTS)
    }

    const t2 = performance.now()
    times.push(t2 - t1)
    resultCount = results.length
  }
  times.sort((a, b) => a - b)
  const median = times[1]
  console.log(
    `  ${query.padEnd(20)} ${String(resultCount).padStart(8)} ${(median.toFixed(1) + 'ms').padStart(10)} ${(times.map(t => t.toFixed(1)).join('/') + 'ms').padStart(14)}`
  )
}

// --- Summary ---
console.log(`\n${'='.repeat(50)}`)
console.log(`  SUMMARY`)
console.log(`${'='.repeat(50)}`)
console.log(`  Engine:           MiniSearch (two-tier)`)
console.log(`  Resource entries: ${resourceEntries.length.toLocaleString()}`)
console.log(`  Column entries:   ${columnEntries.length.toLocaleString()}`)
console.log(`  Index JSON:       ${(indexJson.length / 1024 / 1024).toFixed(1)} MB`)
console.log(`  Init time:        ${initTimes[1].toFixed(0)}ms`)
console.log()
