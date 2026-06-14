with channel_totals as (
    select
        channel,
        sum(impressions) as impressions,
        sum(clicks) as clicks,
        sum(spend_usd) as spend_usd,
        sum(leads) as leads
    from {{ ref('int_marketing_daily_spend') }}
    group by 1
)

select
    channel,
    impressions,
    clicks,
    spend_usd,
    leads,
    round(spend_usd / nullif(leads, 0), 2) as customer_acquisition_cost_usd,
    round(clicks / nullif(impressions, 0), 4) as click_through_rate,
    round(leads / nullif(clicks, 0), 4) as lead_conversion_rate
from channel_totals
