select
    rating_id,
    ticket_id,
    requester_member_id,
    assignee_id,
    score,
    comment,
    created_at
from {{ source('zendesk', 'satisfaction_ratings') }}
