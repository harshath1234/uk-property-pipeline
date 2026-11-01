-- One row per current sale. Attributes that can differ between two sales of
-- the same property (type, tenure, new build) live here, not on property.

create table ppd.sale (
    transaction_id  uuid        primary key,
    property_id     bigint      not null references ppd.property (property_id),
    sale_date       date        not null,
    price_gbp       integer     not null check (price_gbp > 0),
    property_type   char(1)     not null references ppd.ref_property_type (code),
    tenure          char(1)     not null references ppd.ref_tenure (code),
    is_new_build    boolean     not null,
    ppd_category    char(1)     not null references ppd.ref_ppd_category (code),
    load_seq        integer     not null,
    loaded_at       timestamptz not null default now()
);

-- Sales arrive roughly in date order, so a tiny BRIN index serves date-range
-- scans; a B-tree on (property_id, sale_date) serves repeat-sale lookups.
create index sale_date_brin on ppd.sale using brin (sale_date);
create index sale_property_date_idx on ppd.sale (property_id, sale_date);
