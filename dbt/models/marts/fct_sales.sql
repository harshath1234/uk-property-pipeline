{{
  config(
    materialized = 'incremental',
    unique_key = 'transaction_id',
    incremental_strategy = 'merge' if target.type == 'bigquery' else 'delete+insert',
    on_schema_change = 'fail',
    post_hook = [
      "{% if is_incremental() %}delete from {{ this }} where transaction_id not in (select transaction_id from {{ ref('stg_transactions') }}){% endif %}"
    ]
  )
}}

-- Grain: one row per current residential sale. Incremental: only rows whose
-- load sequence is newer than anything already in the table are merged, and
-- transactions deleted at source are removed by the post-hook.

select
    s.transaction_id,
    {{ date_key('s.sale_date') }}                                         as date_key,
    {{ surrogate_key(['s.district', 's.county']) }}                       as location_key,
    {{ surrogate_key(['s.property_type_code', 's.tenure_code', 's.is_new_build']) }}
                                                                          as property_key,
    s.ppd_category_code,
    s.postcode_area,
    s.postcode_outward,
    s.price_gbp,
    s.load_seq
from {{ ref('stg_transactions') }} as s
{% if is_incremental() %}
where s.load_seq > (select coalesce(max(load_seq), 0) from {{ this }})
{% endif %}
