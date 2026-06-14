select
    comment_id,
    ticket_id,
    author_id,
    body,
    is_public,
    is_agent_comment,
    created_at
from {{ source('zendesk', 'ticket_comments') }}
