-- Most expensive districts each year, with year-on-year change in median price.
-- Uses: CTE, ordered-set aggregate, LAG, DENSE_RANK, QUALIFY-style filter via subquery.
with yearly as (
    select
        d.district_id,
        d.name                                                     as district,
        extract(year from s.sale_date)::int                        as yr,
        count(*)                                                   as sales,
        percentile_cont(0.5) within group (order by s.price_gbp)   as median_price
    from ppd.sale s
    join ppd.property p on p.property_id = s.property_id
    join ppd.district d on d.district_id = p.district_id
    where s.ppd_category = 'A'
    group by d.district_id, d.name, extract(year from s.sale_date)
    having count(*) >= 30             -- small districts give noisy medians
),
ranked as (
    select
        *,
        median_price / nullif(lag(median_price) over (partition by district_id order by yr), 0)
            - 1                                                    as yoy,
        dense_rank() over (partition by yr order by median_price desc) as price_rank
    from yearly
)
select yr, price_rank, district, sales,
       round(median_price::numeric)        as median_price_gbp,
       round((yoy * 100)::numeric, 1)      as yoy_pct
from ranked
where price_rank <= 10
order by yr, price_rank;
