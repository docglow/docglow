select
    account_id,
    account_number,
    account_name,
    account_type,
    statement_category,
    is_active
from {{ source('quickbooks', 'accounts') }}
