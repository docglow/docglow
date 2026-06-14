select
    event_id,
    anonymous_id,
    user_id,
    member_id,
    page_name,
    page_path,
    page_url,
    referrer_url,
    occurred_at,
    device_type,
    platform
from {{ source('segment', 'pages') }}
