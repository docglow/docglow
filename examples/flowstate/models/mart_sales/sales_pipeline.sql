select
    o.owner_name,
    o.sales_team,
    o.owner_region,
    o.stage_name,
    count(*) as opportunity_count,
    sum(case when o.is_closed = false then 1 else 0 end) as open_count,
    sum(case when o.is_won = true then 1 else 0 end) as won_count,
    sum(case when o.is_closed = true and o.is_won = false then 1 else 0 end) as lost_count,
    sum(o.amount_arr_usd) as total_arr_usd,
    sum(case when o.is_closed = false then o.amount_arr_usd else 0 end) as open_arr_usd,
    sum(case when o.is_won = true then o.amount_arr_usd else 0 end) as won_arr_usd,
    sum(case when o.is_closed = false then o.weighted_arr_usd else 0 end) as weighted_open_arr_usd
from {{ ref('int_sales_opportunities_enriched') }} o
group by 1, 2, 3, 4
