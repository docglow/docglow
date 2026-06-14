select
    ad_id,
    ad_set_id,
    campaign_id,
    ad_name,
    ad_status,
    creative_format,
    landing_page_url,
    created_at,
    updated_at
from {{ source('facebook_ads', 'ads') }}
