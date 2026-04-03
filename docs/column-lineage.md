# Column-Level Lineage

Docglow can trace column-level dependencies across your dbt project by parsing compiled SQL with [sqlglot](https://github.com/tobymao/sqlglot). This shows you exactly which upstream columns feed into each downstream column, with transformation labels (direct, rename, derived, aggregated).

## Setup

Install the column-lineage extra:

```bash
pip install "docglow[column-lineage]"
```

Column lineage is **enabled by default** when sqlglot is installed. To disable it:

```bash
docglow generate --skip-column-lineage
```

Or in `docglow.yml`:

```yaml
column_lineage: false
```

## How It Works

1. Docglow reads the compiled SQL from each model's `manifest.json` entry
2. sqlglot parses the SQL into an AST and traces column references through JOINs, CTEs, subqueries, and SELECT expressions
3. Results are cached in `.docglow-column-lineage-cache.json` (keyed by SQL hash) so subsequent runs only analyze changed models
4. The frontend renders column-level edges on the lineage graph with color-coded transformation labels

## Analyzing Specific Models

For large projects (75+ models), a full column lineage analysis can take several minutes. Use `--column-lineage-select` to scope the analysis to a specific model and its dependencies:

```bash
# Analyze fct_orders and everything upstream of it
docglow generate --column-lineage-select +fct_orders

# Analyze fct_orders and everything downstream of it
docglow generate --column-lineage-select fct_orders+

# Analyze both upstream and downstream (default)
docglow generate --column-lineage-select fct_orders
```

### Direction syntax

| Pattern | Meaning |
|---------|---------|
| `fct_orders` | The model and both upstream + downstream dependencies |
| `+fct_orders` | The model and its upstream (parents, grandparents, etc.) |
| `fct_orders+` | The model and its downstream (children, grandchildren, etc.) |

### Limiting depth

By default, `--column-lineage-select` traces all hops in the selected direction. Use `--column-lineage-depth` to limit how far it goes:

```bash
# Analyze fct_orders and up to 2 hops upstream
docglow generate --column-lineage-select +fct_orders --column-lineage-depth 2

# Analyze dim_customer and 1 hop in each direction
docglow generate --column-lineage-select dim_customer --column-lineage-depth 1
```

`--column-lineage-depth` requires `--column-lineage-select`. It has no effect on full project analysis.

### Incremental analysis

Results from `--column-lineage-select` accumulate in the cache file. You can analyze different parts of your project in separate runs:

```bash
# First run: analyze the orders subgraph
docglow generate --column-lineage-select +fct_orders

# Second run: add the customers subgraph (cache preserves orders results)
docglow generate --column-lineage-select +dim_customer

# The site now has column lineage for both subgraphs
```

This is the recommended workflow for large projects — start with your most important models and expand coverage over time.

## Large Project Guidance

When your project has 75 or more models, Docglow prints a time estimate before running column lineage:

```
Column lineage: ~450 columns across 120 models (est. ~15 min)
Tip: Use --column-lineage-select <model> to analyze a subgraph.
```

**Recommendations for large projects:**

| Project size | Approach |
|-------------|----------|
| < 75 models | Full analysis runs automatically, usually under 1 minute |
| 75–200 models | Full analysis works but may take 5–15 minutes. Consider `--column-lineage-select` for faster iteration |
| 200–500 models | Use `--column-lineage-select` for incremental analysis. Full analysis may take 30+ minutes |
| 500+ models | Always use `--column-lineage-select`. Run full analysis only in CI with caching |

### CI optimization

In CI, cache the lineage results between runs:

```yaml
# .github/workflows/docs.yml
- name: Cache column lineage
  uses: actions/cache@v4
  with:
    path: .docglow-column-lineage-cache.json
    key: docglow-col-lineage-${{ hashFiles('target/manifest.json') }}
    restore-keys: docglow-col-lineage-

- name: Generate docs
  run: docglow generate --project-dir . --output-dir ./site
```

The cache file is keyed by SQL hash, so only models with changed SQL are re-analyzed on each run.

## Transformation Types

Column lineage edges are labeled with transformation types:

| Type | Color | Meaning | Example |
|------|-------|---------|---------|
| **direct** | Green | Column is passed through unchanged | `SELECT customer_id FROM stg_customers` |
| **rename** | Green | Column is renamed but value unchanged | `SELECT customer_id AS cust_id` |
| **passthrough** | Green | Column comes from `SELECT *` | `SELECT * FROM stg_orders` |
| **derived** | Amber | Column is transformed by an expression | `SELECT UPPER(name) AS name` |
| **aggregated** | Purple | Column uses an aggregate function | `SELECT COUNT(*) AS order_count` |
| **unknown** | Amber | Transformation couldn't be determined | Complex Jinja or unresolvable SQL |

## Supported SQL Dialects

Column lineage parsing supports these SQL dialects (auto-detected from your dbt adapter):

| Adapter | Dialect | Notes |
|---------|---------|-------|
| PostgreSQL | `postgres` | Full support |
| Snowflake | `snowflake` | Includes `VARIANT` access (`obj:key::type`), `SELECT * EXCLUDE(...)` |
| BigQuery | `bigquery` | Full support |
| DuckDB | `duckdb` | Full support |
| Redshift | `redshift` | Full support |
| Databricks | `databricks` | Full support |
| Spark | `spark` | Full support |
| Trino / Starburst | `trino` | Full support |
| Athena | `presto` | Mapped to Presto dialect |
| SQL Server / Fabric | `tsql` | Full support |
| Oracle | `oracle` | Full support |

## Troubleshooting

### Models with no column lineage

Some models may not have column lineage if:

- **No compiled SQL available** — run `dbt compile` to generate compiled SQL in `manifest.json`
- **Complex Jinja macros** — custom macros and `dbt_utils.pivot()` are replaced with `NULL` if compiled SQL is unavailable
- **Dynamic tables** — models using `CREATE DYNAMIC TABLE` may not have parseable SQL, but CTE column resolution can still resolve some columns

Check `.docglow-column-lineage-failures.log` for details on models that couldn't be fully analyzed. Common entries:

```
model.my_project.stg_events: OptimizeError — Could not resolve column "variant_col:key"
model.my_project.mart_summary: ParseError — Unresolvable Jinja: {{ some_macro() }}
```

### Clearing the cache

If column lineage results seem stale:

```bash
rm .docglow-column-lineage-cache.json
docglow generate
```

### Disabling for specific models

There's no per-model disable flag yet. If a specific model causes issues, you can:

1. Use `--column-lineage-select` to exclude it by analyzing only the models you care about
2. Report the issue — we're actively improving SQL parsing coverage
