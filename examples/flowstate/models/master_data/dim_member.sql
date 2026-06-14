select
    m.member_id,
    m.studio_id,
    st.studio_name,
    st.region,
    m.first_name,
    m.last_name,
    m.email,
    m.status as member_status,
    m.joined_date,
    datediff('day', m.joined_date, current_date) as tenure_days
from {{ ref('stg_app_db__members') }} m
left join {{ ref('stg_app_db__studios') }} st on m.studio_id = st.studio_id
