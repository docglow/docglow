select
    i.instructor_id,
    i.studio_id,
    st.studio_name,
    st.region,
    i.first_name,
    i.last_name,
    i.email,
    i.specialty,
    i.hired_date,
    i.is_active
from {{ ref('stg_app_db__instructors') }} i
left join {{ ref('stg_app_db__studios') }} st on i.studio_id = st.studio_id
