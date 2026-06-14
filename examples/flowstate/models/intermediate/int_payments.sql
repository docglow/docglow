select
    ch.charge_id,
    m.member_id,
    m.studio_id,
    ch.amount as amount_usd,
    ch.currency,
    ch.status as charge_status,
    ch.created_at as charged_at,
    ch.refunded
from {{ ref('stg_stripe__charges') }} ch
left join {{ ref('stg_app_db__members') }} m on ch.customer_email = m.email
