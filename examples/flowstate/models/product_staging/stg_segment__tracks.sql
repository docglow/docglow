select
    event_id,
    anonymous_id,
    user_id,
    member_id,
    event_name,
    occurred_at,
    received_at,
    device_type,
    platform,
    app_version,
    properties_json
from {{ source('segment', 'tracks') }}
