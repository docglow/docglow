select
    o.opportunity_id,
    o.opportunity_name,
    o.account_id,
    a.account_name,
    a.industry,
    a.studio_count,
    a.billing_state_code as account_state_code,
    o.owner_id,
    u.full_name as owner_name,
    u.sales_team,
    u.region as owner_region,
    o.stage_name,
    o.amount_arr_usd,
    o.probability,
    o.amount_arr_usd * o.probability as weighted_arr_usd,
    o.lead_source,
    o.forecast_category,
    o.is_won,
    o.is_closed,
    o.created_at,
    o.close_date
from {{ ref('stg_salesforce__opportunities') }} o
left join {{ ref('stg_salesforce__accounts') }} a on o.account_id = a.account_id
left join {{ ref('stg_salesforce__users') }} u on o.owner_id = u.user_id
