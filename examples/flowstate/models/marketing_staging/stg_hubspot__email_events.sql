select
    email_event_id,
    email_campaign_id,
    contact_id,
    event_type,
    event_date as date_day,
    device_type,
    created_at
from {{ source('hubspot', 'email_events') }}
