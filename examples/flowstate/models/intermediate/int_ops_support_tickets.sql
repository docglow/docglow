select
    t.ticket_id,
    t.requester_member_id,
    t.assignee_id,
    a.name as assignee_name,
    a.role as assignee_role,
    t.status,
    t.priority,
    t.channel,
    t.ticket_type,
    t.created_at,
    t.solved_at,
    datediff('hour', t.created_at, t.solved_at) as resolution_hours,
    t.satisfaction_score,
    r.score as csat_rating,
    r.comment as csat_comment
from {{ ref('stg_zendesk__tickets') }} t
left join {{ ref('stg_zendesk__users') }} a on t.assignee_id = a.user_id
left join {{ ref('stg_zendesk__satisfaction_ratings') }} r on t.ticket_id = r.ticket_id
