select
    campaign_id,
    campaign_name,
    campaign_objective,
    campaign_status,
    daily_budget_usd,
    buying_type,
    start_time,
    stop_time,
    created_at,
    updated_at
from {{ source('facebook_ads', 'campaigns') }}
