select
    ticket_id,
    requester_member_id,
    assignee_id,
    subject,
    status,
    priority,
    channel,
    ticket_type,
    created_at,
    updated_at,
    solved_at,
    satisfaction_score
from {{ source('zendesk', 'tickets') }}
