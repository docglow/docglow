select
    user_id,
    full_name,
    email,
    role_name,
    sales_team,
    manager_id,
    region,
    quota_arr_usd,
    is_active,
    created_at
from {{ source('salesforce', 'users') }}
