select
    session_id,
    anonymous_id,
    user_id,
    member_id,
    session_started_at,
    session_ended_at,
    duration_seconds,
    event_count,
    entry_page_path,
    exit_page_path,
    device_type,
    platform
from {{ source('segment', 'sessions') }}
