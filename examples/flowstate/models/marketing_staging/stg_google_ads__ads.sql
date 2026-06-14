select
    ad_id,
    ad_group_id,
    campaign_id,
    ad_type,
    ad_status,
    headline,
    final_url,
    created_at,
    updated_at
from {{ source('google_ads', 'ads') }}
