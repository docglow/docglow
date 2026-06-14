with feature_events as (
    select
        member_id,
        case
            when event_name in ('booked_class', 'viewed_schedule', 'cancelled_booking') then 'scheduling'
            when event_name in ('checked_in', 'scanned_qr') then 'check_in'
            when event_name in ('purchased_membership', 'upgraded_plan', 'viewed_pricing') then 'membership'
            when event_name in ('viewed_progress', 'logged_workout', 'set_goal') then 'fitness_tracking'
            else 'other'
        end as feature_area,
        event_name,
        occurred_at
    from {{ ref('stg_segment__tracks') }}
    where member_id is not null
)

select
    fe.feature_area,
    fe.member_id,
    dm.region as member_region,
    dm.member_status,
    count(*) as event_count,
    count(distinct fe.event_name) as distinct_actions,
    min(fe.occurred_at) as first_used_at,
    max(fe.occurred_at) as last_used_at
from feature_events fe
left join {{ ref('dim_member') }} dm on fe.member_id = dm.member_id
group by 1, 2, 3, 4
