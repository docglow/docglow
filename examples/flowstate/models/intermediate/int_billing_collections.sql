select
    t.transaction_id,
    t.invoice_id,
    t.subscription_id,
    t.member_id,
    m.member_name,
    m.studio_id,
    t.transaction_type,
    t.status as transaction_status,
    t.amount_usd as transaction_amount_usd,
    t.payment_method,
    t.gateway,
    t.processed_at,
    cn.credit_note_id,
    coalesce(cn.amount_refunded_usd, 0) as amount_refunded_usd,
    cn.reason_code as credit_reason_code
from {{ ref('stg_chargebee__transactions') }} t
left join {{ ref('stg_chargebee__credit_notes') }} cn on t.invoice_id = cn.invoice_id
left join {{ ref('dim_member') }} m on t.member_id = m.member_id
