select
    invoice_id,
    subscription_id,
    member_id,
    status,
    total_usd,
    coalesce(amount_paid_usd, 0) as amount_paid_usd,
    coalesce(amount_due_usd, 0) as amount_due_usd,
    currency,
    issued_at,
    due_at,
    paid_at,
    created_at
from {{ source('chargebee', 'invoices') }}
