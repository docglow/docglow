select
    c.*,
    k.*
from {{ ref('stg_companies') }} as c
join {{ ref('stg_contracts') }} as k
    on c.company_id = k.company_id
