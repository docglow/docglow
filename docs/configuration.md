# Configuration

Docglow works out of the box with zero configuration. For customization, add a `docglow.yml` to your dbt project root.

## Generate a Starter Config

```bash
docglow init
```

This creates a `docglow.yml` with all options documented and commented out.

## Full Configuration Reference

```yaml
# docglow.yml
version: 1
title: "My dbt Project"       # Custom site title
theme: auto                     # auto | light | dark
slim: false                     # Omit SQL from output to reduce file size
column_lineage: true            # Enable column-level lineage (default: true)
enable_erd: false               # Render the /erd view (default: false). See docs/erd.md

health:
  weights:
    documentation: 0.25         # Weight for documentation coverage
    testing: 0.25               # Weight for test coverage
    freshness: 0.15             # Weight for source freshness
    complexity: 0.15            # Weight for model complexity
    naming: 0.10                # Weight for naming conventions
    orphans: 0.10               # Weight for orphan detection

  naming_rules:                  # Keys are layer names (matched against folder names)
    staging: "^stg_"            # Regex for staging models
    intermediate: "^int_"       # Regex for intermediate models
    marts: "^fct_|^dim_"        # Regex for mart models (fact or dimension)
    # Add any custom layers:
    # base: "^base_"            # Regex for base models

  complexity:
    high_sql_lines: 200         # Max SQL lines before flagging
    high_join_count: 8          # Max joins before flagging
    high_cte_count: 10          # Max CTEs before flagging
    high_subquery_count: 5      # Max subqueries before flagging

profiling:
  enabled: false                # Enable column profiling
  sample_size: 10000            # Max rows to sample per model
  cache: true                   # Cache profiling results

ai:
  enabled: false                # Enable AI chat panel
  model: claude-sonnet-4        # Anthropic model to use

insights:
  enabled: true                 # Enable column insights (semantic type inference)
  descriptions: append          # append | replace | skip

lineage_layers:
  layers:
    - name: source
      rank: 0
      color: "#dcfce7"
    - name: staging
      rank: 1
      color: "#dbeafe"
    - name: intermediate
      rank: 2
      color: "#fef3c7"
    - name: mart
      rank: 3
      color: "#fce7f3"
    - name: exposure
      rank: 4
      color: "#f3e8ff"

ui:
  lineage_badge:
    abbreviation: smart           # smart | truncate | middle | none
    max_model_chars: 30           # Max chars before the model name is shortened
    max_column_chars: 22          # Max chars before the column name is shortened
  sidebar:
    default_width: 256            # Default navigation width in pixels
    min_width: 180                # Minimum resizable navigation width
    max_width: 480                # Maximum resizable navigation width
    resizable: true               # Allow users to drag the navigation width
  table_layout:
    mode: auto                    # auto | scroll | fit
    min_width: null               # Optional global table min-width in pixels
    content_sized_columns:        # Columns that size to their content first
      - column
      - type
      - tests
    content_sized_max_width: 360  # Maximum width for content-sized columns
```

## Theme

Docglow supports three themes: `auto` (follows system preference), `light`, and `dark`.

```bash
docglow generate --theme dark
```

Or in `docglow.yml`:

```yaml
theme: dark
```

## Health Scoring

See [Health Scoring](health-scoring.md) for detailed documentation of each dimension, weight rationale, and customization.

## Lineage Layers

See [Customizing Lineage Layers](lineage-layers.md) for a complete guide on defining custom layers and rules, including a real-world example.

## Column Lineage

See [Column-Level Lineage](column-lineage.md) for setup, incremental analysis, and troubleshooting.

## Lineage badge display

The column-level lineage column on a model page renders a small pill for each upstream/downstream reference. When your project has long snake_case names (e.g. `fact_orders_by_supplier_over_time_by_state_and_segment`), those pills can grow wide enough to overlap adjacent UI. `ui.lineage_badge.abbreviation` controls how the name is shortened in the compact form. The full name always remains available in the tooltip and on row hover.

| Strategy   | What it does | Example (`fact_orders_by_supplier_over_time_by_state_and_segment`) |
|---|---|---|
| `smart` *(default)* | Keeps a readable prefix and suffix with a middle ellipsis | `fact_orders_by_supplie…segment` |
| `truncate` | Keeps the first N characters and appends `…` — simplest and closest to `dbt docs` behavior | `fact_orders_by_supplier_over_t...` |
| `middle` | Keeps both the prefix (`fct_` / `stg_`) and the suffix, inserting `…` in the middle | `fact_orders_by_supplie…segment` |
| `none` | Renders the full name; relies on the badge's CSS max-width plus the tooltip for overflow | `fact_orders_by_supplier_over_time_by_state_and_segment` |

`max_model_chars` and `max_column_chars` set the character threshold at which abbreviation kicks in (they have no effect on `none`). Defaults are 30 and 22 respectively; raise them if you want longer names to render in full, lower them if you want more aggressive shortening.

!!! tip
    Not sure which to pick? Start with `smart` (the default) because it keeps the label recognisable without letting long names dominate the row.
    If your team expects names to match `dbt docs` output exactly, switch to `truncate`.

## Layout

The `ui.sidebar` section controls the default navigation width and resize bounds.
Use it when your project has deeply nested folders or long model names that need more navigation space.

```yaml
ui:
  sidebar:
    default_width: 320
    min_width: 220
    max_width: 560
    resizable: true
```

The `ui.table_layout` section controls how wide operational tables are allowed to be before they scroll or fit into the available content area.

| Mode | Behaviour |
|---|---|
| `auto` *(default)* | Tables use their page-specific minimum width and scroll only when the available space is smaller. |
| `scroll` | Tables keep their minimum width and always expose horizontal overflow when needed. |
| `fit` | Tables fit the available space, truncating long text where the page defines fixed numeric columns. |

Set `min_width` to override page-specific table minimums globally.
Set `content_sized_columns` when dense tables should reserve room for important fields before the description column takes the remaining space.
The Columns tab currently recognises `column`, `type`, `lineage`, and `tests`.

```yaml
ui:
  table_layout:
    mode: auto
    min_width: 1120
    content_sized_columns: [column, type, tests]
    content_sized_max_width: 360
```
