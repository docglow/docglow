select
    i.invoice_id,
    i.subscription_id,
    i.member_id,
    m.member_name,
    i.status as invoice_status,
    i.total_usd,
    i.amount_paid_usd,
    i.amount_due_usd,
    i.currency,
    i.issued_at,
    d.date_day as issued_date,
    d.fiscal_month,
    i.due_at,
    i.paid_at
from {{ ref('stg_chargebee__invoices') }} i
left join {{ ref('dim_member') }} m on i.member_id = m.member_id
left join {{ ref('dim_date') }} d on cast(i.issued_at as date) = d.date_day
