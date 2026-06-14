select
    email_campaign_id,
    campaign_name,
    subject_line,
    from_name,
    email_type,
    send_date,
    num_recipients,
    created_at,
    updated_at
from {{ source('hubspot', 'email_campaigns') }}
