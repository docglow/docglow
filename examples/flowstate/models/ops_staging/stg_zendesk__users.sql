select
    user_id,
    name,
    email,
    role,
    organization_id,
    time_zone,
    is_active,
    created_at
from {{ source('zendesk', 'users') }}
