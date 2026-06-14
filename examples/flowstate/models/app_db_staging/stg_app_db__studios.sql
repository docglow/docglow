select
    studio_id,
    studio_name,
    region,
    city,
    state_code,
    timezone,
    opened_date,
    is_active,
    created_at,
    updated_at
from {{ source('app_db', 'studios') }}
