select
    booking_id,
    schedule_id,
    class_id,
    studio_id,
    member_id,
    instructor_id,
    class_start_at,
    booking_status,
    booked_at,
    checked_in_at,
    is_no_show,
    case when checked_in_at is not null then 1 else 0 end as is_attended
from {{ ref('int_bookings') }}
