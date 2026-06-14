select
    opportunity_id,
    opportunity_name,
    account_id,
    owner_id,
    stage_name,
    amount_arr_usd,
    probability,
    lead_source,
    forecast_category,
    is_won,
    is_closed,
    created_at,
    close_date
from {{ source('salesforce', 'opportunities') }}
