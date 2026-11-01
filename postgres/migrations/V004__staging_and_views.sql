-- Unlogged staging table for bulk COPY (fast, not crash-safe, rebuilt every load).
create schema if not exists staging;

create unlogged table staging.sale_load (
    transaction_id    uuid,
    price             bigint,
    sale_date         date,
    postcode          text,
    postcode_outward  text,
    postcode_area     text,
    property_type     text,
    is_new_build      boolean,
    tenure            text,
    paon              text,
    saon              text,
    street            text,
    locality          text,
    town_city         text,
    district          text,
    county            text,
    ppd_category      text,
    load_seq          integer
);

-- Denormalised read view for analysts.
create view ppd.v_sale_detail as
select
    s.transaction_id,
    s.sale_date,
    s.price_gbp,
    pt.label  as property_type,
    tn.label  as tenure,
    s.is_new_build,
    s.ppd_category,
    p.postcode,
    pc.outward_code,
    d.name    as district,
    c.name    as county,
    p.property_id
from ppd.sale s
join ppd.property p          on p.property_id = s.property_id
join ppd.district d          on d.district_id = p.district_id
join ppd.county c            on c.county_id = d.county_id
left join ppd.postcode pc    on pc.postcode = p.postcode
join ppd.ref_property_type pt on pt.code = s.property_type
join ppd.ref_tenure tn       on tn.code = s.tenure;
