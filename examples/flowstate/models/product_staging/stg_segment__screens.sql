select
    event_id,
    anonymous_id,
    user_id,
    member_id,
    screen_name,
    screen_category,
    occurred_at,
    device_type,
    platform,
    app_version
from {{ source('segment', 'screens') }}
