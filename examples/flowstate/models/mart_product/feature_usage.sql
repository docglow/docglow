with adoption as (
    select
        feature_area,
        member_id,
        member_region,
        event_count,
        distinct_actions,
        first_used_at,
        last_used_at
    from {{ ref('int_product_feature_adoption') }}
),

member_base as (
    select count(distinct member_id) as total_members
    from {{ ref('dim_member') }}
)

select
    a.feature_area,
    a.member_region,
    count(distinct a.member_id) as adopting_members,
    max(mb.total_members) as total_members,
    round(count(distinct a.member_id) / nullif(max(mb.total_members), 0), 4) as adoption_rate,
    sum(a.event_count) as total_feature_events,
    round(avg(a.distinct_actions), 2) as avg_distinct_actions_per_member,
    max(a.last_used_at) as most_recent_use_at
from adoption a
cross join member_base mb
group by 1, 2
