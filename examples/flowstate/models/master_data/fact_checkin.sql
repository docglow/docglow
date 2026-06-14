select
    booking_id,
    schedule_id,
    class_id,
    studio_id,
    member_id,
    instructor_id,
    class_start_at,
    checked_in_at,
    date_trunc('day', checked_in_at) as checkin_date,
    datediff('minute', booked_at, checked_in_at) as minutes_from_booking_to_checkin
from {{ ref('int_bookings') }}
where checked_in_at is not null
