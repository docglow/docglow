# starshop

A tiny dbt + DuckDB project whose only job is to exercise **qualified star
expansion** in column-level lineage.

## Why this exists

Column lineage has to expand `renamed.*` and `a.* / b.*` into real columns. Neither
of the other example projects does that in an outermost `SELECT` — across 445 models
there was not a single case — so a regression here was invisible to both the test
suite and the demo site. `starshop` makes it visible.

`dim_company` covers the single-star case:

```sql
with renamed as (
    select * from {{ ref('stg_companies') }}
)
select
    md5(company_name) as company_key,
    renamed.*
from renamed
```

Only `company_key` is written out. The other four columns exist solely because
`renamed.*` expands, so if expansion breaks, this model drops to one traced column.

`fct_company_contracts` covers the multi-star join:

```sql
select c.*, k.*
from {{ ref('stg_companies') }} as c
join {{ ref('stg_contracts') }} as k on c.company_id = k.company_id
```

Each star must resolve against its own source. If they collapse to one source, or
to nothing, this model loses its column lineage entirely. It also produces a
genuine name collision on `company_id`, which the warehouse disambiguates as
`company_id_1`.

## Regenerating the artifacts

`target/` is committed so CI never needs a warehouse, matching `jaffle-shop`.
Regenerate after changing a model:

```bash
cd examples/starshop
DBT_PROFILES_DIR=. dbt build
DBT_PROFILES_DIR=. dbt docs generate
rm -f starshop.duckdb            # gitignored, but keep the tree clean
```

## Viewing it

```bash
docglow generate --project-dir examples/starshop --output-dir /tmp/starshop-site
docglow serve --dir /tmp/starshop-site
```

Open `dim_company` in the lineage view and click any column other than
`company_key`. Each one should trace back to `stg_companies` through a
`passthrough` edge.
