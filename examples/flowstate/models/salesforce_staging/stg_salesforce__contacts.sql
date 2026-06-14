select
    contact_id,
    account_id,
    first_name,
    last_name,
    email,
    phone,
    title,
    contact_role,
    is_primary_contact,
    lead_source,
    created_at,
    updated_at
from {{ source('salesforce', 'contacts') }}
