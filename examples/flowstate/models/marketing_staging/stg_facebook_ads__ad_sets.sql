select
    ad_set_id,
    campaign_id,
    ad_set_name,
    ad_set_status,
    optimization_goal,
    daily_budget_usd,
    targeting_audience,
    created_at,
    updated_at
from {{ source('facebook_ads', 'ad_sets') }}
