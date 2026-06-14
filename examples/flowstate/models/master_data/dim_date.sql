with date_spine as (
    select dateadd(day, seq4(), '2022-01-01'::date) as date_day
    from table(generator(rowcount => 1461))
)

select
    date_day,
    year(date_day) as year,
    month(date_day) as month_number,
    day(date_day) as day_of_month,
    dayofweek(date_day) as day_of_week,
    to_char(date_day, 'YYYY-MM') as year_month,
    to_char(date_day, 'Mon') as month_name,
    case when dayofweek(date_day) in (0, 6) then true else false end as is_weekend,
    date_trunc('month', date_day) as first_day_of_month,
    date_trunc('quarter', date_day) as first_day_of_quarter
from date_spine
