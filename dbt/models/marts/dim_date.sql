-- Calendar dimension covering every day from the first to the last sale.
with bounds as (
    select min(sale_date) as first_day, max(sale_date) as last_day
    from {{ ref('stg_transactions') }}
),

spine as (
    {{ date_spine("(select first_day from bounds)", "(select last_day from bounds)") }}
)

select
    {{ date_key('date_day') }}                       as date_key,
    date_day,
    extract(year from date_day)                      as year,
    extract(quarter from date_day)                   as quarter,
    extract(month from date_day)                     as month,
    {{ dbt.date_trunc('month', 'date_day') }}        as month_start,
    case when extract(month from date_day) >= 4
         then extract(year from date_day)
         else extract(year from date_day) - 1 end    as uk_tax_year_start
from spine
