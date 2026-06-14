select
    opportunity_history_id,
    opportunity_id,
    from_stage_name,
    to_stage_name,
    amount_arr_usd,
    probability,
    changed_by_user_id,
    is_stage_change,
    created_at
from {{ source('salesforce', 'opportunity_history') }}
