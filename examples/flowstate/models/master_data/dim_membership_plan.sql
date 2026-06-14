select
    p.plan_id,
    p.studio_id,
    st.studio_name,
    p.plan_name,
    p.plan_tier,
    p.billing_interval,
    p.monthly_price_usd,
    p.included_class_credits,
    p.is_active
from {{ ref('stg_app_db__membership_plans') }} p
left join {{ ref('stg_app_db__studios') }} st on p.studio_id = st.studio_id
