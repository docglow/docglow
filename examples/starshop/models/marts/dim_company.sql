with renamed as (
    select * from {{ ref('stg_companies') }}
)
select
    md5(company_name) as company_key,
    renamed.*
from renamed
