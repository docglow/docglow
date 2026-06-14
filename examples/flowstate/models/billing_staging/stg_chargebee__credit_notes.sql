select
    credit_note_id,
    invoice_id,
    subscription_id,
    member_id,
    status,
    reason_code,
    total_usd,
    amount_refunded_usd,
    amount_allocated_usd,
    currency,
    issued_at,
    created_at
from {{ source('chargebee', 'credit_notes') }}
