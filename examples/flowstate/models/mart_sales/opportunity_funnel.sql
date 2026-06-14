select
    o.stage_name,
    o.forecast_category,
    count(*) as opportunity_count,
    count(distinct o.account_id) as account_count,
    sum(o.amount_arr_usd) as total_arr_usd,
    avg(o.amount_arr_usd) as avg_arr_usd,
    avg(o.probability) as avg_probability,
    sum(o.weighted_arr_usd) as weighted_arr_usd,
    sum(case when o.is_won = true then 1 else 0 end) as won_count,
    sum(case when o.is_closed = true and o.is_won = false then 1 else 0 end) as lost_count
from {{ ref('int_sales_opportunities_enriched') }} o
group by 1, 2
