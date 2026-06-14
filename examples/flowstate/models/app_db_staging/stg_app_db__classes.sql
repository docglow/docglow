select
    class_id,
    studio_id,
    class_name,
    class_type,
    duration_minutes,
    capacity,
    is_active
from {{ source('app_db', 'classes') }}
