with daily as (
    select
        activity_date,
        member_id,
        member_region,
        session_count,
        total_events,
        total_duration_seconds
    from {{ ref('int_product_daily_active_members') }}
)

select
    d.activity_date,
    d.member_region,
    count(distinct d.member_id) as daily_active_members,
    count(distinct case
        when d.member_id is not null then d.member_id end) as active_members,
    sum(d.session_count) as total_sessions,
    sum(d.total_events) as total_events,
    round(avg(d.total_duration_seconds), 1) as avg_session_seconds_per_member,
    round(sum(d.total_events) / nullif(count(distinct d.member_id), 0), 2) as events_per_active_member
from daily d
group by 1, 2
