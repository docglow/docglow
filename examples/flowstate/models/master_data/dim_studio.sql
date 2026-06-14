select
    studio_id,
    studio_name,
    region,
    city,
    state_code,
    timezone,
    opened_date,
    is_active
from {{ ref('stg_app_db__studios') }}
