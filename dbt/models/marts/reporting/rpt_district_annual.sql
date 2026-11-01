-- District x year: volume, median price and year-on-year change (window function).
with yearly as (
    select
        l.district,
        l.county,
        d.year,
        count(*)                       as sales,
        {{ median('f.price_gbp') }}    as median_price_gbp
    from {{ ref('fct_sales') }} as f
    join {{ ref('dim_date') }} as d on f.date_key = d.date_key
    join {{ ref('dim_location') }} as l on f.location_key = l.location_key
    where f.ppd_category_code = 'A'
    group by l.district, l.county, d.year
)

select
    *,
    lag(median_price_gbp) over (partition by district, county order by year) as prev_median_gbp,
    case
        when lag(median_price_gbp) over (partition by district, county order by year) > 0
        then median_price_gbp * 1.0
             / lag(median_price_gbp) over (partition by district, county order by year) - 1
    end as median_yoy_change,
    rank() over (partition by year order by median_price_gbp desc) as price_rank_in_year
from yearly
