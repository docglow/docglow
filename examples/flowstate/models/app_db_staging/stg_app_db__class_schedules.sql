select
    schedule_id,
    class_id,
    studio_id,
    instructor_id,
    start_at,
    end_at,
    room,
    booked_count,
    capacity
from {{ source('app_db', 'class_schedules') }}
