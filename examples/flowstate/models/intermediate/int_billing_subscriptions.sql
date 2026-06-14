select
    s.subscription_id,
    s.member_id,
    m.member_name,
    m.studio_id,
    st.studio_name,
    st.region,
    s.plan_id,
    p.plan_name,
    p.plan_tier,
    p.price_usd as plan_price_usd,
    s.status as subscription_status,
    s.billing_period,
    s.billing_period_unit,
    s.mrr_usd,
    s.started_at,
    s.activated_at,
    s.cancelled_at
from {{ ref('stg_chargebee__subscriptions') }} s
left join {{ ref('stg_chargebee__subscription_plans') }} p on s.plan_id = p.plan_id
left join {{ ref('dim_member') }} m on s.member_id = m.member_id
left join {{ ref('dim_studio') }} st on m.studio_id = st.studio_id
