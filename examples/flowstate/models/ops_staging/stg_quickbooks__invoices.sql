select
    invoice_id,
    customer_id,
    issued_at,
    due_at,
    paid_at,
    total_usd,
    balance_usd,
    invoice_status
from {{ source('quickbooks', 'invoices') }}
