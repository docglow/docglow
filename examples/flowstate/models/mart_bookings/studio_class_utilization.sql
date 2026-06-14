select
    s.studio_id,
    s.studio_name,
    s.region,
    cl.class_type,
    count(*) as total_bookings,
    sum(fb.is_attended) as attended,
    sum(case when fb.is_no_show then 1 else 0 end) as no_shows,
    sum(fb.is_attended) / nullif(count(*), 0) as attendance_rate
from {{ ref('fact_booking') }} fb
left join {{ ref('dim_studio') }} s on fb.studio_id = s.studio_id
left join {{ ref('dim_class') }} cl on fb.class_id = cl.class_id
group by 1, 2, 3, 4
