select
    h.opportunity_history_id,
    h.opportunity_id,
    o.opportunity_name,
    o.account_id,
    h.from_stage_name,
    h.to_stage_name,
    h.amount_arr_usd,
    h.probability,
    h.changed_by_user_id,
    u.full_name as changed_by_name,
    h.is_stage_change,
    o.is_won,
    o.is_closed,
    h.created_at as transition_at
from {{ ref('stg_salesforce__opportunity_history') }} h
left join {{ ref('stg_salesforce__opportunities') }} o on h.opportunity_id = o.opportunity_id
left join {{ ref('stg_salesforce__users') }} u on h.changed_by_user_id = u.user_id
