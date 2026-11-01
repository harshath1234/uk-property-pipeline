-- Location hierarchy and properties (third normal form: every non-key
-- attribute depends on the key, the whole key and nothing but the key).

create table ppd.county (
    county_id   integer generated always as identity primary key,
    name        text not null unique
);

create table ppd.district (
    district_id integer generated always as identity primary key,
    name        text    not null,
    county_id   integer not null references ppd.county (county_id),
    unique (name, county_id)
);
create index district_county_idx on ppd.district (county_id);

create table ppd.town (
    town_id     integer generated always as identity primary key,
    name        text not null unique
);

create table ppd.postcode (
    postcode      varchar(8)  primary key,
    outward_code  varchar(4)  not null,
    area          varchar(2)  not null,
    check (postcode = upper(postcode))
);
create index postcode_outward_idx on ppd.postcode (outward_code);

-- A property is identified by its address. NULLS NOT DISTINCT (PostgreSQL 15+)
-- makes two addresses with a blank flat number (saon) count as the same key.
create table ppd.property (
    property_id  bigint generated always as identity primary key,
    postcode     varchar(8)  references ppd.postcode (postcode),
    paon         text,
    saon         text,
    street       text,
    locality     text,
    town_id      integer references ppd.town (town_id),
    district_id  integer not null references ppd.district (district_id),
    constraint property_address_uk unique nulls not distinct
        (postcode, paon, saon, street, district_id)
);
create index property_district_idx on ppd.property (district_id);
-- expression index matching the loader's null-safe address join
create index property_address_match_idx on ppd.property
    (district_id, coalesce(postcode, ''), coalesce(paon, ''), coalesce(saon, ''),
     coalesce(street, ''));
create index property_postcode_idx on ppd.property (postcode);
