# Customizing Lineage Layers

Docglow groups your dbt models into **layers** (e.g. `source`, `staging`, `mart`) to organize the lineage graph and validate naming conventions. Every project is different — this guide shows how to customize layers to match your project's structure.

## Two systems, one config file

Layer behavior is driven by two separate sections of `docglow.yml`:

| Section | Purpose | Affects |
|---|---|---|
| `lineage_layers` | Defines layers (name, rank, color) and how nodes map to them | The lineage graph (colored bands, left-to-right ordering) |
| `health.naming_rules` | Regex patterns that model names must match for each layer | The Naming dimension of the health score |

You can configure either or both. They're independent — a layer can exist in the graph without a naming rule, and vice versa.

## Create `docglow.yml`

`docglow.yml` is not created automatically. Generate a starter config with:

```bash
docglow init
```

This writes a `docglow.yml` to your dbt project root with all options commented out. Uncomment the sections you want to customize.

## Defining lineage layers

The `lineage_layers` section has two parts: **`layers`** (definitions) and **`rules`** (matchers that assign nodes to layers).

### Layers

Each layer has a `name`, `rank` (integer or float — lower = further left in the graph), and `color` (hex, used for the background band):

```yaml
lineage_layers:
  layers:
    - name: source
      rank: 0
      color: "#dcfce7"
    - name: staging
      rank: 1
      color: "#dbeafe"
    - name: mart
      rank: 3
      color: "#fce7f3"
```

!!! tip
    Ranks don't need to be whole numbers. If you want to insert a layer between `staging` (rank 1) and `mart` (rank 3), use `rank: 2` — or even `rank: 1.5` if you don't want to renumber the others.

### Rules

Rules map individual models to a layer. Each rule has a `layer`, a `match` type, and a `pattern`. **The first matching rule wins** — order matters.

| Match type | What it matches | Example pattern |
|---|---|---|
| `schema` | The node's schema (glob syntax) | `mart_*`, `dw_*`, `raw` |
| `folder` | The node's folder path (glob syntax) | `*staging*`, `models/base` |
| `tag` | A dbt tag on the node | `finance`, `pii` |
| `name_prefix` | Start of the model name | `stg_`, `fct_`, `base_` |
| `name_suffix` | End of the model name | `_prep`, `_seed` |
| `name_glob` | Full name glob match | `*_summary`, `stg_finance_*` |

After rules, these fallbacks apply:

1. `resource_type == "source"` or `"seed"` → `source` layer
2. `resource_type == "exposure"` → highest-rank layer
3. Anything still unresolved is auto-assigned based on neighbor ranks in the lineage graph

!!! warning "Auto-assignment is a fallback, not a feature"
    If you see models in unexpected layers, it usually means no rule matched and they were auto-assigned by neighbor rank. Add an explicit rule to fix it.

## Naming rules

Each entry in `health.naming_rules` maps a **layer name** (matched against folder segments) to a **regex pattern** the model name must match.

```yaml
health:
  naming_rules:
    staging: "^stg_"
    intermediate: "^int_"
    marts: "^fct_|^dim_"
    base: "^base_"
```

Layer names are matched against folder segments in the model's path (e.g. `models/billing/base/base_invoice.sql` → detected as layer `base` if the path contains a `base` segment). Naming rules work independently of `lineage_layers` — they drive the health score's Naming dimension.

## A real-world example

Here's the `docglow.yml` from a production dbt project that uses a custom layer structure — `source` → `prep` → `intermediate` → `transform` → `mart` → `exposure`:

```yaml
version: 1

lineage_layers:
  layers:
    - name: source
      rank: 0
      color: "#dcfce7"
    - name: prep
      rank: 1
      color: "#dbeafe"
    - name: intermediate
      rank: 1.5           # Between prep and transform — no renumbering needed
      color: "#ffd700"
    - name: transform
      rank: 2
      color: "#fef3c7"
    - name: mart
      rank: 3
      color: "#fce7f3"
    - name: exposure
      rank: 4
      color: "#f3e8ff"

  rules:
    # Schema-based rules — checked first because they're the most specific
    - layer: transform
      match: schema
      pattern: "master_data"
    - layer: intermediate
      match: schema
      pattern: "dw_*"
    - layer: mart
      match: schema
      pattern: "mart_*"
    - layer: mart
      match: schema
      pattern: "master_reporting"
    - layer: prep
      match: schema
      pattern: "prep_*"

    # Folder-based rules — fallback for nodes not matched by schema
    - layer: prep
      match: folder
      pattern: "*_prep"
    - layer: intermediate
      match: folder
      pattern: "dw*"
    - layer: transform
      match: folder
      pattern: "master_data*"
    - layer: mart
      match: folder
      pattern: "mart*"

    # Name prefix rules — catches models that don't match by schema or folder
    - layer: prep
      match: name_prefix
      pattern: "stg_"
    - layer: intermediate
      match: name_prefix
      pattern: "int_"
    - layer: mart
      match: name_prefix
      pattern: "fct_"
    - layer: mart
      match: name_prefix
      pattern: "dim_"

    # Name suffix rules — final fallback
    - layer: prep
      match: name_suffix
      pattern: "_prep"
    - layer: source
      match: name_suffix
      pattern: "_seed"
```

### Why this ordering matters

This config demonstrates a useful pattern: **most specific match first**. Schema-based rules are checked first because schemas are usually authoritative (e.g. anything in `mart_*` schema is definitely a mart, regardless of naming). Folder rules come next — they catch models grouped by directory. Name-based rules come last as a fallback for anything not caught by the first two.

If you flipped the order (name rules first), a model named `stg_orders` that lives in a `mart_*` schema would be assigned to `prep` instead of `mart` — almost certainly not what you want.

## Troubleshooting

**Models are in the "auto" layer (not assigned by a rule).**
No rule matched the model. Add a `folder`, `schema`, or `name_prefix` rule that covers it. The frontend shows whether a layer assignment came from a rule or from auto-assignment.

**My custom layer shows up in naming compliance as "0% compliant".**
You have `naming_rules` for a layer but no models match the folder segment. Check that your folder structure actually contains a path segment matching the layer name (e.g. `models/base/` for a `base` layer).

**Ranks collide (two layers at the same rank).**
Docglow orders by rank ascending; layers with identical ranks are ordered by declaration order. If you want strict ordering, give each layer a unique rank.

**Model is in a Windows-style path and isn't matching.**
This was a bug fixed in v0.7.2 — upgrade with `pip install --upgrade docglow`.

## See also

- [Configuration reference](configuration.md) — full `docglow.yml` schema
- [Health Scoring](health-scoring.md) — how the Naming dimension feeds the health score
