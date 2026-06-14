select
    c.class_id,
    c.studio_id,
    st.studio_name,
    c.class_name,
    c.class_type,
    c.duration_minutes,
    c.capacity,
    c.is_active
from {{ ref('stg_app_db__classes') }} c
left join {{ ref('stg_app_db__studios') }} st on c.studio_id = st.studio_id
