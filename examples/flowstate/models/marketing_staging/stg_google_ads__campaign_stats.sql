select
    campaign_stat_id,
    campaign_id,
    stat_date as date_day,
    impressions,
    clicks,
    cost_usd,
    conversions,
    created_at
from {{ source('google_ads', 'campaign_stats') }}
