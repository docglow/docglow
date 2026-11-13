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
    hover_detail: inline          # inline | panel
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
| `smart` *(default)* | Collapses leading snake_case segments to single-letter initials joined by `·`, keeping the distinguishing tail intact | `f·o·b·s·o·t·b·s·a·segment` |
| `truncate` | Keeps the first N characters and appends `…` — simplest and closest to `dbt docs` behavior | `fact_orders_by_supplier_over_t...` |
| `middle` | Keeps both the prefix (`fct_` / `stg_`) and the suffix, inserting `…` in the middle | `fact_orders_by_supplie…segment` |
| `none` | Renders the full name; relies on the badge's CSS max-width plus the tooltip for overflow | `fact_orders_by_supplier_over_time_by_state_and_segment` |

`max_model_chars` and `max_column_chars` set the character threshold at which abbreviation kicks in (they have no effect on `none`). Defaults are 30 and 22 respectively; raise them if you want longer names to render in full, lower them if you want more aggressive shortening.

!!! tip
    Not sure which to pick? Start with `smart` (the default) — it preserves the most unique part of the name. If your team expects names to match `dbt docs` output exactly, switch to `truncate`.

`ui.lineage_badge.hover_detail` controls how a shortened badge reveals its full name on hover.

| Value | What it does |
|---|---|
| `inline` *(default)* | Hovering anywhere on the row expands each shortened badge in place, which makes the row taller while the pointer is over it |
| `panel` | Hovering or focusing a badge opens a floating panel with the full model name, column name, and transformation type. The panel sits outside the table, so the row height never changes |

In `panel` mode a badge also gets the panel when no name was shortened but the combined `model.column` text is too long to fit the pill.

`hover_detail` does not change how names are shortened. `abbreviation: middle` already gives middle-ellipsis names, and pairing it with `hover_detail: panel` gives the look from [#130](https://github.com/docglow/docglow/pull/130):

```yaml
ui:
  lineage_badge:
    abbreviation: middle
    hover_detail: panel
```
