select
    charge_id,
    member_id,
    studio_id,
    amount_usd,
    currency,
    charge_status,
    charged_at,
    refunded,
    case
        when charge_status = 'succeeded' and not refunded then amount_usd
        else 0
    end as net_revenue_usd
from {{ ref('int_payments') }}
