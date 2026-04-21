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
