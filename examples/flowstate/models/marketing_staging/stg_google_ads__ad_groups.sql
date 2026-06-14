select
    ad_group_id,
    campaign_id,
    ad_group_name,
    ad_group_status,
    ad_group_type,
    cpc_bid_usd,
    created_at,
    updated_at
from {{ source('google_ads', 'ad_groups') }}
