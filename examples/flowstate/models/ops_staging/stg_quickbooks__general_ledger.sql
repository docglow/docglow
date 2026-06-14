select
    entry_id,
    account_id,
    posted_at,
    transaction_type,
    memo,
    amount_usd,
    debit_credit,
    department_id
from {{ source('quickbooks', 'general_ledger') }}
