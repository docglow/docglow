# Health Scoring

Docglow computes a health score (0–100) for your dbt project across six dimensions. Each dimension measures a different aspect of project quality.

## Dimensions

| Dimension | Default Weight | What it measures |
|-----------|---------------|-----------------|
| **Documentation** | 25% | Percentage of models and columns with descriptions |
| **Testing** | 25% | Percentage of models and columns with at least one test |
| **Freshness** | 15% | Source freshness check pass rate (excluded when no sources are monitored) |
| **Complexity** | 15% | Percentage of models below complexity thresholds (SQL lines, joins, CTEs) |
| **Naming** | 10% | Percentage of models following naming conventions (`stg_`, `int_`, `fct_`, `dim_`) |
| **Orphans** | 10% | Percentage of models that have at least one downstream consumer |

### Why these weights?

Documentation and testing carry the highest weight (25% each) because they have the most direct impact on team productivity. A well-documented, well-tested project is discoverable and trustworthy.

Freshness and complexity are weighted at 15% each — they're important signals but are less universally applicable. Not every project uses source freshness monitoring, and complexity thresholds are subjective.

Naming and orphans carry 10% each. Naming conventions improve consistency but are team-specific. Orphan detection catches forgotten models but some orphans are intentional (e.g., reporting endpoints).

### Freshness handling

When no sources in your project have freshness monitoring configured, the freshness dimension is **excluded entirely** from the weighted score. Its weight is redistributed proportionally to the other dimensions. This prevents projects without source freshness from getting an artificial score boost.

## Grades

| Grade | Score range |
|-------|------------|
| A | 90–100 |
| B | 80–89 |
| C | 70–79 |
| D | 60–69 |
| F | 0–59 |

## Customizing weights

Override the default weights in your `docglow.yml`:

```yaml
health:
  weights:
    documentation: 0.30   # Increase docs weight
    testing: 0.30          # Increase test weight
    freshness: 0.10
    complexity: 0.10
    naming: 0.10
    orphans: 0.10
```

Weights should sum to 1.0. If they don't, the score will still compute but may exceed 100 or fall short.

## Customizing thresholds

### Complexity thresholds

```yaml
health:
  complexity:
    high_sql_lines: 200    # Max SQL lines before flagging (default: 200)
    high_join_count: 8      # Max joins before flagging (default: 8)
    high_cte_count: 10      # Max CTEs before flagging (default: 10)
    high_subquery_count: 5  # Max subqueries before flagging (default: 5)
```

### Naming conventions

```yaml
health:
  naming_rules:
    staging: "^stg_"           # Regex for staging models (default: ^stg_)
    intermediate: "^int_"      # Regex for intermediate models (default: ^int_)
    marts: "^fct_|^dim_"       # Regex for mart models (default: ^fct_ or ^dim_)
    # Custom layers — keys are matched against folder names in your dbt project:
    # base: "^base_"           # Models in a "base" folder must match ^base_
```

!!! note
    Layer names are matched against folder segments in your dbt project path.
    You can define any layer name — it will be matched when a model's folder
    path contains a segment with that exact name. For backwards compatibility,
    `marts_fact` and `marts_dimension` keys are merged into a single `marts` layer.

## CLI usage

```bash
# Print health report to terminal
docglow health

# Output as markdown (for PR comments)
docglow health --format markdown

# Fail CI if score is below threshold
docglow generate --fail-under 80
```
