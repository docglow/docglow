select
    m.membership_id,
    m.member_id,
    m.plan_id,
    p.plan_tier,
    p.studio_id,
    m.status,
    m.started_at,
    m.ended_at,
    m.auto_renew,
    m.monthly_price_usd,
    datediff('day', m.started_at, coalesce(m.ended_at, current_date)) as active_days,
    case when m.status = 'active' then 1 else 0 end as is_active
from {{ ref('stg_app_db__memberships') }} m
left join {{ ref('stg_app_db__membership_plans') }} p on m.plan_id = p.plan_id
