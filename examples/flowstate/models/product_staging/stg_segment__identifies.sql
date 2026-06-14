select
    event_id,
    anonymous_id,
    user_id,
    member_id,
    email,
    trait_plan_tier,
    trait_signup_source,
    identified_at,
    device_type,
    platform
from {{ source('segment', 'identifies') }}
