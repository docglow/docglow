#!/usr/bin/env node
/**
 * Benchmark Fuse.js search performance against a generated docglow-data.json.
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

// Fuse.js is installed in the frontend directory
const require = createRequire(
  resolve(process.cwd(), 'frontend', 'node_modules', 'fuse.js', 'package.json')
)
const Fuse = require('fuse.js').default ?? require('fuse.js')

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
const t0 = performance.now()
const raw = readFileSync(dataPath, 'utf-8')
const tParse = performance.now()
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
console.log(`  JSON parse:       ${(tJson - tParse).toFixed(0)}ms`)
console.log(`  Total entries:    ${searchIndex.length.toLocaleString()}`)
console.log(`  Resource entries: ${resourceEntries.length.toLocaleString()}`)
console.log(`  Column entries:   ${columnEntries.length.toLocaleString()}`)
console.log(`  Index JSON size:  ${(indexJson.length / 1024 / 1024).toFixed(1)} MB`)

// Check which fields are present
const sampleResource = resourceEntries[0] || {}
const sampleColumn = columnEntries[0] || {}
console.log(`  Resource fields:  ${Object.keys(sampleResource).join(', ')}`)
console.log(`  Column fields:    ${Object.keys(sampleColumn).join(', ')}`)

// --- Detect Fuse options based on fields present ---
const hasColumns = 'columns' in sampleResource
const hasSqlSnippet = 'sql_snippet' in sampleResource

const keys = [
  { name: 'name', weight: 0.4 },
  { name: 'column_name', weight: 0.35 },
  { name: 'description', weight: 0.25 },
  ...(hasColumns ? [{ name: 'columns', weight: 0.15 }] : []),
  { name: 'model_name', weight: 0.1 },
  { name: 'tags', weight: 0.1 },
  ...(hasSqlSnippet ? [{ name: 'sql_snippet', weight: 0.1 }] : []),
]

// --- Benchmark: Index construction ---
console.log(`\n--- Index Construction ---`)
console.log(`  Fuse keys:        ${keys.map(k => k.name).join(', ')}`)

// Run 3 times and take median
const initTimes = []
let fuse
for (let i = 0; i < 3; i++) {
  const t1 = performance.now()
  fuse = new Fuse(searchIndex, {
    keys,
    threshold: 0.4,
    includeMatches: hasColumns, // old behavior had includeMatches
    minMatchCharLength: 2,
  })
  const t2 = performance.now()
  initTimes.push(t2 - t1)
}
initTimes.sort((a, b) => a - b)
console.log(`  Init times:       ${initTimes.map(t => t.toFixed(0) + 'ms').join(', ')}`)
console.log(`  Median init:      ${initTimes[1].toFixed(0)}ms`)

// --- Benchmark: Search queries ---
console.log(`\n--- Search Queries ---`)
console.log(`  ${'Query'.padEnd(20)} ${'Results'.padStart(8)} ${'Time'.padStart(10)} ${'Avg (3 runs)'.padStart(14)}`)
console.log(`  ${'─'.repeat(20)} ${'─'.repeat(8)} ${'─'.repeat(10)} ${'─'.repeat(14)}`)

for (const query of queries) {
  const times = []
  let resultCount = 0
  for (let i = 0; i < 3; i++) {
    const t1 = performance.now()
    const results = fuse.search(query, { limit: 20 })
    const t2 = performance.now()
    times.push(t2 - t1)
    resultCount = results.length
  }
  times.sort((a, b) => a - b)
  const median = times[1]
  console.log(
    `  ${query.padEnd(20)} ${String(resultCount).padStart(8)} ${(median.toFixed(1) + 'ms').padStart(10)} ${(times.map(t => t.toFixed(0)).join('/') + 'ms').padStart(14)}`
  )
}

// --- Summary ---
console.log(`\n${'='.repeat(50)}`)
console.log(`  SUMMARY`)
console.log(`${'='.repeat(50)}`)
console.log(`  Index entries:    ${searchIndex.length.toLocaleString()}`)
console.log(`  Index JSON:       ${(indexJson.length / 1024 / 1024).toFixed(1)} MB`)
console.log(`  Init time:        ${initTimes[1].toFixed(0)}ms`)
console.log(`  Fuse keys:        ${keys.length}`)
console.log(`  includeMatches:   ${hasColumns}`)
console.log(`  Has sql_snippet:  ${hasSqlSnippet}`)
console.log(`  Has columns:      ${hasColumns}`)
console.log()
