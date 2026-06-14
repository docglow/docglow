select
    account_id,
    account_name,
    industry,
    studio_count,
    billing_city,
    billing_state_code,
    billing_country,
    annual_revenue_usd,
    employee_count,
    account_owner_id,
    account_type,
    is_customer,
    created_at,
    updated_at
from {{ source('salesforce', 'accounts') }}
