-- One row per local authority district (within its county).
select
    {{ surrogate_key(['district', 'county']) }} as location_key,
    district,
    county,
    count(*)                                   as transactions_to_date
from {{ ref('stg_transactions') }}
group by district, county
