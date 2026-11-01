-- Gaps and islands: the longest run of consecutive months in which a
-- district's median price rose, month on month.
-- Uses: date_trunc, LAG, ROW_NUMBER difference trick to group consecutive rows.
with monthly as (
    select
        p.district_id,
        date_trunc('month', s.sale_date)::date                       as month,
        percentile_cont(0.5) within group (order by s.price_gbp)     as median_price
    from ppd.sale s
    join ppd.property p on p.property_id = s.property_id
    where s.ppd_category = 'A'
    group by p.district_id, date_trunc('month', s.sale_date)
),
flagged as (
    select *,
           median_price > lag(median_price) over (partition by district_id order by month) as rose
    from monthly
),
islands as (
    select *,
           row_number() over (partition by district_id order by month)
         - row_number() over (partition by district_id, rose order by month) as grp
    from flagged
),
streaks as (
    select district_id, min(month) as streak_start, max(month) as streak_end,
           count(*) as months_rising
    from islands
    where rose
    group by district_id, grp
)
select d.name as district, s.streak_start, s.streak_end, s.months_rising
from streaks s
join ppd.district d on d.district_id = s.district_id
order by s.months_rising desc, d.name
limit 20;
