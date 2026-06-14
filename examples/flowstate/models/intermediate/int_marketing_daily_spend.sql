with ad_performance as (
    select
        channel,
        campaign_id,
        campaign_name,
        date_day,
        impressions,
        clicks,
        spend_usd,
        leads
    from {{ ref('int_marketing_ad_performance') }}
)

select
    ap.date_day,
    d.day_of_week,
    d.month_name,
    ap.channel,
    ap.campaign_id,
    ap.campaign_name,
    sum(ap.impressions) as impressions,
    sum(ap.clicks) as clicks,
    sum(ap.spend_usd) as spend_usd,
    sum(ap.leads) as leads
from ad_performance ap
left join {{ ref('dim_date') }} d
    on ap.date_day = d.date_day
group by 1, 2, 3, 4, 5, 6
