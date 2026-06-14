select
    charge_id,
    customer_email,
    amount,
    currency,
    status,
    created_at,
    refunded
from {{ source('stripe', 'charges') }}
