-- Monthly sales volume and prices by property type (standard-price sales only,
-- category A, which is how HM Land Registry's own statistics are usually cut).
select
    d.month_start,
    p.property_type,
    count(*)                         as sales,
    {{ median('f.price_gbp') }}      as median_price_gbp,
    avg(f.price_gbp)                 as mean_price_gbp
from {{ ref('fct_sales') }} as f
join {{ ref('dim_date') }} as d on f.date_key = d.date_key
join {{ ref('dim_property') }} as p on f.property_key = p.property_key
where f.ppd_category_code = 'A'
group by d.month_start, p.property_type
