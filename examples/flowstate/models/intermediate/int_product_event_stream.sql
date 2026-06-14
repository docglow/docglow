with tracks as (
    select
        event_id,
        member_id,
        event_name,
        'track' as event_category,
        occurred_at,
        device_type,
        platform
    from {{ ref('stg_segment__tracks') }}
),

pages as (
    select
        event_id,
        member_id,
        page_name as event_name,
        'page' as event_category,
        occurred_at,
        device_type,
        platform
    from {{ ref('stg_segment__pages') }}
),

screens as (
    select
        event_id,
        member_id,
        screen_name as event_name,
        'screen' as event_category,
        occurred_at,
        device_type,
        platform
    from {{ ref('stg_segment__screens') }}
),

unioned as (
    select event_id, member_id, event_name, event_category, occurred_at, device_type, platform from tracks
    union all
    select event_id, member_id, event_name, event_category, occurred_at, device_type, platform from pages
    union all
    select event_id, member_id, event_name, event_category, occurred_at, device_type, platform from screens
)

select
    u.event_id,
    u.member_id,
    dm.region as member_region,
    dm.member_status,
    u.event_name,
    u.event_category,
    u.occurred_at,
    cast(u.occurred_at as date) as event_date,
    u.device_type,
    u.platform
from unioned u
left join {{ ref('dim_member') }} dm on u.member_id = dm.member_id
