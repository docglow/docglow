with spend as (
    select
        channel,
        campaign_id,
        campaign_name,
        sum(impressions) as impressions,
        sum(clicks) as clicks,
        sum(spend_usd) as spend_usd,
        sum(leads) as leads
    from {{ ref('int_marketing_daily_spend') }}
    group by 1, 2, 3
)

select
    channel,
    campaign_id,
    campaign_name,
    impressions,
    clicks,
    spend_usd,
    leads,
    round(spend_usd / nullif(clicks, 0), 2) as cost_per_click_usd,
    round(spend_usd / nullif(leads, 0), 2) as cost_per_lead_usd,
    round(clicks / nullif(impressions, 0), 4) as click_through_rate
from spend
