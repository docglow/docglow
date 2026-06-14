select
    employee_id,
    full_name,
    work_email,
    department,
    role,
    manager_id,
    location,
    employment_type,
    hired_at,
    terminated_at
from {{ source('rippling', 'employees') }}
