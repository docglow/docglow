select
    plan_id,
    studio_id,
    plan_name,
    plan_tier,
    billing_interval,
    monthly_price_usd,
    included_class_credits,
    is_active
from {{ source('app_db', 'membership_plans') }}
