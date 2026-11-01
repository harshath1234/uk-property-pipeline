# Entity relationship diagrams

## PostgreSQL: normalised operational model (`postgres/migrations/`)

```mermaid
erDiagram
    COUNTY ||--o{ DISTRICT : contains
    DISTRICT ||--o{ PROPERTY : contains
    TOWN |o--o{ PROPERTY : "postal town of"
    POSTCODE |o--o{ PROPERTY : "addressed at"
    PROPERTY ||--o{ SALE : "sold in"
    REF_PROPERTY_TYPE ||--o{ SALE : classifies
    REF_TENURE ||--o{ SALE : classifies
    REF_PPD_CATEGORY ||--o{ SALE : classifies

    COUNTY { int county_id PK
             text name UK }
    DISTRICT { int district_id PK
               text name
               int county_id FK }
    TOWN { int town_id PK
           text name UK }
    POSTCODE { varchar postcode PK
               varchar outward_code
               varchar area }
    PROPERTY { bigint property_id PK
               varchar postcode FK
               text paon
               text saon
               text street
               text locality
               int town_id FK
               int district_id FK }
    SALE { uuid transaction_id PK
           bigint property_id FK
           date sale_date
           int price_gbp
           char property_type FK
           char tenure FK
           bool is_new_build
           char ppd_category FK
           int load_seq }
    REF_PROPERTY_TYPE { char code PK
                        text label }
    REF_TENURE { char code PK
                 text label }
    REF_PPD_CATEGORY { char code PK
                       text label }
```

Why the attributes sit where they do:
- Property type, tenure and new-build flag are on **SALE**, not PROPERTY: the
  same address can be sold as a new build once and as established later, and
  conversions change type.
- **PROPERTY** has a natural key of (postcode, PAON, SAON, street, district)
  enforced with `UNIQUE NULLS NOT DISTINCT`, plus a surrogate `property_id`.

## Warehouse: star schema (`dbt/models/marts/`)

```mermaid
erDiagram
    DIM_DATE ||--o{ FCT_SALES : date_key
    DIM_LOCATION ||--o{ FCT_SALES : location_key
    DIM_PROPERTY ||--o{ FCT_SALES : property_key

    FCT_SALES { string transaction_id PK
                int date_key FK
                string location_key FK
                string property_key FK
                string ppd_category_code
                string postcode_area
                string postcode_outward
                bigint price_gbp
                int load_seq }
    DIM_DATE { int date_key PK
               date date_day
               int year
               int quarter
               int month
               date month_start
               int uk_tax_year_start }
    DIM_LOCATION { string location_key PK
                   string district
                   string county }
    DIM_PROPERTY { string property_key PK
                   string property_type
                   string tenure
                   bool is_new_build }
```

The warehouse drops street-level address fields: the dashboard only needs
district and postcode area, and HM Land Registry's address data has its own
licence conditions.
