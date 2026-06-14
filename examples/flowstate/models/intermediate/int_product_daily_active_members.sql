with sessions as (
    select
        member_id,
        cast(session_started_at as date) as activity_date,
        session_id,
        duration_seconds,
        event_count,
        platform
    from {{ ref('stg_segment__sessions') }}
    where member_id is not null
)

select
    s.activity_date,
    s.member_id,
    dm.region as member_region,
    dm.member_status,
    count(distinct s.session_id) as session_count,
    sum(s.event_count) as total_events,
    sum(s.duration_seconds) as total_duration_seconds,
    max(s.platform) as last_platform
from sessions s
left join {{ ref('dim_member') }} dm on s.member_id = dm.member_id
group by 1, 2, 3, 4
