select
    member_id,
    studio_id,
    first_name,
    last_name,
    email,
    phone,
    date_of_birth,
    joined_date,
    status,
    created_at,
    updated_at
from {{ source('app_db', 'members') }}
