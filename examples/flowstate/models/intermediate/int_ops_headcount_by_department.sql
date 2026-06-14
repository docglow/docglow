select
    e.department,
    d.cost_center,
    d.org_group,
    count(e.employee_id) as total_employees,
    count(case when e.terminated_at is null then e.employee_id end) as active_employees,
    count(case when e.terminated_at is not null then e.employee_id end) as terminated_employees,
    min(e.hired_at) as earliest_hire_at,
    max(e.hired_at) as latest_hire_at
from {{ ref('stg_rippling__employees') }} e
left join {{ ref('stg_rippling__departments') }} d on e.department = d.department_name
group by 1, 2, 3
