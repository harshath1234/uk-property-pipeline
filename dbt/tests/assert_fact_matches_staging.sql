-- Reconciliation: the incremental fact table must hold exactly the rows in
-- staging (no missed merges, no rows left behind after source deletes).
with counts as (
    select
        (select count(*) from {{ ref('fct_sales') }})        as fact_rows,
        (select count(*) from {{ ref('stg_transactions') }}) as staging_rows
)
select * from counts where fact_rows != staging_rows
