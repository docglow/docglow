select
    s.studio_id,
    s.studio_name,
    s.region,
    date_trunc('day', fp.charged_at) as revenue_date,
    sum(fp.net_revenue_usd) as net_revenue_usd,
    count(distinct fp.member_id) as paying_members
from {{ ref('fact_payment') }} fp
left join {{ ref('dim_studio') }} s on fp.studio_id = s.studio_id
group by 1, 2, 3, 4
