-- Junk dimension: every combination of property type, tenure and new-build flag.
with combos as (
    select pt.property_type_code, pt.property_type, t.tenure_code, t.tenure, nb.is_new_build
    from {{ ref('property_types') }} as pt
    cross join {{ ref('tenures') }} as t
    cross join (select true as is_new_build union all select false) as nb
)

select
    {{ surrogate_key(['property_type_code', 'tenure_code', 'is_new_build']) }} as property_key,
    property_type_code,
    property_type,
    tenure_code,
    tenure,
    is_new_build
from combos
