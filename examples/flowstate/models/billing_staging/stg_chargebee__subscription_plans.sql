select
    plan_id,
    plan_name,
    plan_tier,
    status,
    price_usd,
    billing_period,
    billing_period_unit,
    trial_period_days,
    is_metered,
    created_at,
    updated_at
from {{ source('chargebee', 'subscription_plans') }}
