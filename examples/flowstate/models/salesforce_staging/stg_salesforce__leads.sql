select
    lead_id,
    first_name,
    last_name,
    email,
    company_name,
    lead_source,
    lead_status,
    industry,
    estimated_studio_count,
    owner_id,
    is_converted,
    converted_account_id,
    converted_opportunity_id,
    created_at,
    converted_at
from {{ source('salesforce', 'leads') }}
