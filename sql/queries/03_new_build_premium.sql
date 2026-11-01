-- New-build premium by county and property type: median new-build price vs
-- median established price for the same type, same county, same year.
-- Uses: FILTER clause on aggregates, CTE, ratio guarded by NULLIF.
with stats as (
    select
        c.name                                                       as county,
        s.property_type,
        extract(year from s.sale_date)::int                          as yr,
        count(*) filter (where s.is_new_build)                       as new_sales,
        count(*) filter (where not s.is_new_build)                   as old_sales,
        percentile_cont(0.5) within group (order by s.price_gbp)
            filter (where s.is_new_build)                            as new_median,
        percentile_cont(0.5) within group (order by s.price_gbp)
            filter (where not s.is_new_build)                        as old_median
    from ppd.sale s
    join ppd.property p on p.property_id = s.property_id
    join ppd.district d on d.district_id = p.district_id
    join ppd.county c   on c.county_id = d.county_id
    where s.ppd_category = 'A' and s.property_type in ('D', 'S', 'T', 'F')
    group by c.name, s.property_type, extract(year from s.sale_date)
)
select county, property_type, yr, new_sales, old_sales,
       round(((new_median / nullif(old_median, 0) - 1) * 100)::numeric, 1) as new_build_premium_pct
from stats
where new_sales >= 20 and old_sales >= 20
order by yr desc, new_build_premium_pct desc nulls last;
