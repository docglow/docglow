select
    transaction_id,
    invoice_id,
    subscription_id,
    member_id,
    transaction_type,
    status,
    amount_usd,
    currency,
    payment_method,
    gateway,
    processed_at,
    created_at
from {{ source('chargebee', 'transactions') }}
