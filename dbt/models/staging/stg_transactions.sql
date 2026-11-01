-- One row per current transaction, with clean names and types.
select
    transaction_id,
    cast(price as {{ dbt.type_bigint() }})          as price_gbp,
    cast(sale_date as date)                         as sale_date,
    cast(sale_year as {{ dbt.type_int() }})         as sale_year,
    cast(sale_month as {{ dbt.type_int() }})        as sale_month,
    postcode,
    postcode_outward,
    postcode_area,
    property_type                                   as property_type_code,
    is_new_build,
    tenure                                          as tenure_code,
    town_city,
    district,
    county,
    ppd_category                                    as ppd_category_code,
    cast(load_seq as {{ dbt.type_int() }})          as load_seq
from {{ source('silver', 'silver_transactions') }}
