select
    campaign_id,
    campaign_name,
    campaign_status,
    advertising_channel_type,
    budget_amount_usd,
    bidding_strategy,
    start_date,
    end_date,
    created_at,
    updated_at
from {{ source('google_ads', 'campaigns') }}
