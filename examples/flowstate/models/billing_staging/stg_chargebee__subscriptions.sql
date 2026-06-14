select
    subscription_id,
    member_id,
    plan_id,
    status,
    started_at,
    activated_at,
    cancelled_at,
    coalesce(mrr_usd, 0) as mrr_usd,
    billing_period,
    billing_period_unit,
    auto_collection,
    created_at
from {{ source('chargebee', 'subscriptions') }}
