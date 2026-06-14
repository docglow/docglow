select
    contact_id,
    email,
    first_name,
    last_name,
    company_name,
    lifecycle_stage,
    lead_source,
    became_lead_date,
    created_at,
    updated_at
from {{ source('hubspot', 'contacts') }}
