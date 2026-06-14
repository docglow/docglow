select
    b.booking_id,
    b.schedule_id,
    s.class_id,
    c.class_name,
    c.class_type,
    s.studio_id,
    st.studio_name,
    st.region,
    b.member_id,
    m.email as member_email,
    s.instructor_id,
    s.start_at as class_start_at,
    s.end_at as class_end_at,
    b.booking_status,
    b.booked_at,
    b.checked_in_at,
    b.is_no_show
from {{ ref('stg_app_db__bookings') }} b
left join {{ ref('stg_app_db__class_schedules') }} s on b.schedule_id = s.schedule_id
left join {{ ref('stg_app_db__classes') }} c on s.class_id = c.class_id
left join {{ ref('stg_app_db__members') }} m on b.member_id = m.member_id
left join {{ ref('stg_app_db__studios') }} st on s.studio_id = st.studio_id
