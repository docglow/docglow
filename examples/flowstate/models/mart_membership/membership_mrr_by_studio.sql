select
    studio_id,
    studio_name,
    region,
    plan_tier,
    count(distinct subscription_id) as active_subscriptions,
    count(distinct member_id) as active_members,
    sum(mrr_usd) as total_mrr_usd,
    avg(mrr_usd) as avg_mrr_per_subscription_usd,
    sum(mrr_usd) * 12 as annual_run_rate_usd
from {{ ref('int_billing_subscriptions') }}
where subscription_status = 'active'
group by
    studio_id,
    studio_name,
    region,
    plan_tier
