select
    department_id,
    department_name,
    cost_center,
    org_group,
    head_employee_id,
    created_at
from {{ source('rippling', 'departments') }}
