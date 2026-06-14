select
    ad_insight_id,
    campaign_id,
    insight_date as date_day,
    impressions,
    clicks,
    spend_usd,
    leads,
    created_at
from {{ source('facebook_ads', 'ad_insights') }}
