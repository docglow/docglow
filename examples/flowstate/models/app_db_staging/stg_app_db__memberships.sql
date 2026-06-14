select
    membership_id,
    member_id,
    plan_id,
    status,
    started_at,
    ended_at,
    auto_renew,
    monthly_price_usd,
    created_at,
    updated_at
from {{ source('app_db', 'memberships') }}
