select
    l.lead_id,
    l.first_name,
    l.last_name,
    l.email,
    l.company_name,
    l.lead_source,
    l.lead_status,
    l.industry,
    l.estimated_studio_count,
    l.owner_id,
    u.full_name as owner_name,
    u.sales_team,
    l.is_converted,
    l.converted_account_id,
    l.converted_opportunity_id,
    o.stage_name as converted_stage_name,
    o.amount_arr_usd as converted_amount_arr_usd,
    o.is_won as converted_is_won,
    l.created_at,
    l.converted_at
from {{ ref('stg_salesforce__leads') }} l
left join {{ ref('stg_salesforce__users') }} u on l.owner_id = u.user_id
left join {{ ref('stg_salesforce__opportunities') }} o on l.converted_opportunity_id = o.opportunity_id
