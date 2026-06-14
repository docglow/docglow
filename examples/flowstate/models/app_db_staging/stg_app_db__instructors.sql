select
    instructor_id,
    studio_id,
    first_name,
    last_name,
    email,
    specialty,
    hired_date,
    is_active,
    created_at,
    updated_at
from {{ source('app_db', 'instructors') }}
