# Entity-Relationship Diagram (ERD)

Docglow can render an interactive ERD of your dbt project — a visual map of how models relate to each other through foreign keys, with crow's-foot notation showing the cardinality of each relationship.

The ERD is rendered on the `/erd` page when generated, and a 1-hop subgraph appears on each model's page under the **ERD** tab.

[See it on demo.docglow.com →](https://demo.docglow.com/erd){ .md-button }

## Why use the ERD

Most dbt projects don't have an authoritative diagram of their model relationships. Lineage shows *what runs after what*; ERD shows *how rows in one model match rows in another*. Without it, new engineers have to read SQL to understand which `order_id` joins to which `orders.id`, and stakeholders have no way to see the schema at a glance.

The ERD is derived directly from declarations you already have in your project — `relationships` tests, `dbt_constraints` package tests, and dbt `meta` blocks — so it stays in sync with your code without a separate modelling tool.

## Enable the ERD

The ERD is opt-in. Pass `--enable-erd` when generating the site:

```bash
docglow generate --enable-erd
```

Without the flag, the `/erd` route is hidden and no relationship data is included in the payload.

## How relationships are detected

Docglow looks at three sources, in order. Any combination of them works — entries are merged and deduplicated, with conflicts logged.

### 1. Built-in `relationships` tests (recommended)

dbt's built-in `relationships` test is the primary source. If you already have referential integrity tests, your ERD will populate automatically — no extra configuration required.

```yaml
# models/marts/_marts.yml
models:
  - name: orders
    columns:
      - name: customer_id
        tests:
          - relationships:
              to: ref('stg_customers')
              field: customer_id
```

This produces an edge from `orders.customer_id` → `stg_customers.customer_id`. Sources are also supported via `to: source('raw', 'customers')`.

### 2. `dbt_constraints` package tests

If your project uses the [`dbt_constraints`](https://hub.getdbt.com/Snowflake-Labs/dbt_constraints/) package — common in projects that emit physical constraints to the warehouse — Docglow recognizes those declarations too:

```yaml
models:
  - name: orders
    columns:
      - name: customer_id
        tests:
          - dbt_constraints.foreign_key:
              pk_table_name: ref('stg_customers')
              pk_column_name: customer_id
```

Single-column foreign keys only. Composite (model-level) `fk_column_names: [a, b]` declarations are skipped with a debug log.

### 3. `meta.docglow.relationships` (manual override)

When no test exists — or when you want to declare a relationship without enforcing it — add a `meta.docglow.relationships` block to a column. This is the most expressive option and supports forcing a specific cardinality:

```yaml
models:
  - name: order_items
    columns:
      - name: product_id
        meta:
          docglow:
            relationships:
              - to: products
                field: id
                kind: many_to_many   # optional: one_to_one | one_to_many | many_to_many
                severity: warn        # optional: warn | error (defaults to warn)
                label: "via product_variants"  # optional free-text label
```

Notes:

- `to` is the simple model name (no `ref()` wrapper).
- `meta.docglow.relationships` must be declared on a **column**, not at the model level. Model-level declarations are ignored with a debug log.
- If a `relationships` test and a `meta.docglow.relationships` entry both describe the same edge, they merge (`inference_source: "both"`); the test wins on `severity` and run status, the meta entry contributes the `label`.
- If they disagree on the parent model, both are surfaced and a warning is logged naming the file path.

## How cardinality is inferred

Crow's-foot endpoints (`||`, `o|`, `}|`, `}o`) are inferred from the *sibling* tests on the parent and child columns. You don't declare cardinality directly — Docglow reads it off the schema:

| Child column has `not_null`? | Parent column has `unique`? | Child endpoint     | Parent endpoint |
|---|---|---|---|
| yes | yes | `one_and_only_one` (`\|\|`) | `one_or_many` (`}\|`)  |
| yes | no  | `one_and_only_one` (`\|\|`) | `zero_or_many` (`}o`)  |
| no  | yes | `zero_or_one` (`o\|`)       | `one_or_many` (`}\|`)  |
| no  | no  | `zero_or_one` (`o\|`)       | `zero_or_many` (`}o`)  |

`dbt_constraints.primary_key` and `dbt_constraints.unique_key` count as `unique` for this inference, so projects using the constraints package get the same upgrade automatically.

If you want to force a specific cardinality regardless of what tests exist, use `meta.docglow.relationships` with an explicit `kind`:

| `kind` value | Resulting endpoints |
|---|---|
| `one_to_one` | both sides `\|\|` |
| `one_to_many` | child `\|\|`, parent `}\|` |
| `many_to_many` | both sides `}\|` |

## Worked example

The fastest way to get a useful ERD on an existing project is to add three or four `relationships` tests on the join keys you already use:

```yaml
# models/marts/_marts.yml
models:
  - name: orders
    columns:
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('customers')
              field: customer_id

  - name: order_items
    columns:
      - name: order_id
        tests:
          - not_null
          - relationships:
              to: ref('orders')
              field: order_id
      - name: product_id
        tests:
          - relationships:
              to: ref('products')
              field: product_id

  - name: customers
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null
```

After `dbt build && docglow generate --enable-erd`, the ERD will show three edges with proper crow's-foot notation: `order_items` is `}|—||` to `orders` (mandatory many-to-one), and `orders` is `}o—||` to `customers` (optional many-to-one until you add `not_null` on `orders.customer_id`).

## Limitations

- **Single-column foreign keys only.** Composite keys are skipped with a debug log; raise a feature request if you need them.
- **Cross-package `relationships` tests are skipped.** Tests defined in installed packages (e.g. `dbt_expectations.relationships`) are ignored to avoid noise; `dbt_constraints` is the supported exception.
- **Sources can be parents but not children.** A `relationships` test on a model pointing at a source produces an edge; the inverse isn't supported.
- **The `/erd` route is hidden when `--enable-erd` is not set.** No relationship data is included in the generated payload either.

## Troubleshooting

**The ERD page is empty.**
Confirm you generated with `--enable-erd`. If still empty, check that your project has at least one `relationships` test, `dbt_constraints.foreign_key` test, or `meta.docglow.relationships` entry — Docglow only renders edges that come from one of those sources.

**An edge I expected isn't showing up.**
Run `docglow generate --enable-erd -v` (verbose) to surface debug logs. Common causes: cross-package test, composite foreign key, source-as-child, or a typo in the `to:` model name (which produces a "ghost edge" warning for `meta.docglow.relationships`).

**The cardinality is wrong.**
Cardinality follows your tests, not your assumptions. Add `unique` on the parent column to upgrade the parent endpoint to `one_or_many`, and `not_null` on the child column to upgrade the child endpoint to `one_and_only_one`. Or override explicitly with `meta.docglow.relationships` and a `kind`.
