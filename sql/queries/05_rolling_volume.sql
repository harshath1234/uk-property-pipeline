-- Monthly sales volume with a 12-month rolling total and the share of
-- leasehold sales. Uses: frame clause (ROWS BETWEEN), FILTER, date range scan
-- that can use the BRIN index on sale_date.
with monthly as (
    select
        date_trunc('month', sale_date)::date             as month,
        count(*)                                         as sales,
        count(*) filter (where tenure = 'L')             as leasehold_sales
    from ppd.sale
    where sale_date >= date '2018-01-01'
    group by 1
)
select
    month,
    sales,
    sum(sales) over (order by month rows between 11 preceding and current row) as rolling_12m_sales,
    round(100.0 * leasehold_sales / sales, 1)                                  as leasehold_pct
from monthly
order by month;
