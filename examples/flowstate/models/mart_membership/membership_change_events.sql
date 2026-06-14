select
    subscription_id,
    member_id,
    studio_id,
    plan_tier,
    started_at,
    cancelled_at,
    mrr_usd,
    case
        when cancelled_at is not null then 'churn'
        when subscription_status = 'active' and activated_at is not null then 'new'
        when subscription_status = 'active' then 'reactivation'
        else 'other'
    end as change_event_type,
    case
        when cancelled_at is not null then -1 * mrr_usd
        else mrr_usd
    end as mrr_delta_usd
from {{ ref('int_billing_subscriptions') }}
