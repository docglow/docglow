select
    line_item_id,
    invoice_id,
    subscription_id,
    plan_id,
    description,
    line_item_type,
    quantity,
    unit_amount_usd,
    amount_usd,
    is_taxed,
    created_at
from {{ source('chargebee', 'invoice_line_items') }}
