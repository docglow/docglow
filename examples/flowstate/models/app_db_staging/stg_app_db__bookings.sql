select
    booking_id,
    schedule_id,
    member_id,
    booking_status,
    booked_at,
    checked_in_at,
    cancelled_at,
    is_no_show
from {{ source('app_db', 'bookings') }}
