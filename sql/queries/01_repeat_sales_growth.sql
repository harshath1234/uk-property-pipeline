-- Repeat-sales price growth: for properties sold more than once, compare each
-- sale with the previous sale of the same property (LAG), then annualise.
-- Uses: CTEs, LAG window, filtering on a window result, percentile_cont.
-- Index used: sale_property_date_idx (property_id, sale_date).
with ordered as (
    select
        s.property_id,
        s.sale_date,
        s.price_gbp,
        lag(s.sale_date) over w  as prev_date,
        lag(s.price_gbp) over w  as prev_price
    from ppd.sale s
    where s.ppd_category = 'A'
    window w as (partition by s.property_id order by s.sale_date)
),
pairs as (
    select
        property_id,
        sale_date,
        (sale_date - prev_date) / 365.25                          as years_held,
        power(price_gbp::numeric / prev_price, 1 / ((sale_date - prev_date) / 365.25)) - 1
                                                                  as annual_growth
    from ordered
    where prev_date is not null
      and sale_date - prev_date >= 365     -- ignore quick flips and data corrections
)
select
    extract(year from sale_date)::int                                  as resale_year,
    count(*)                                                           as repeat_sales,
    round(avg(years_held)::numeric, 1)                                 as avg_years_held,
    round((percentile_cont(0.5) within group (order by annual_growth) * 100)::numeric, 2)
                                                                       as median_annual_growth_pct
from pairs
group by 1
order by 1;
