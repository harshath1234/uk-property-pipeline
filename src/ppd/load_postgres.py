"""Load the silver layer into the normalised PostgreSQL model.

1. DuckDB reads silver Parquet and writes one CSV (fast, columnar engine).
2. COPY streams it into the unlogged staging table.
3. Set-based upserts fill county -> district -> town -> postcode -> property
   -> sale, inside one transaction. Re-running is safe (ON CONFLICT) and sales
   deleted at source are removed, so Postgres always mirrors silver.

Address columns can be NULL, and `a = b` is never true for NULLs, so joins on
the address use coalesce(col, '') keys. That keeps them hash-joinable, which
`IS NOT DISTINCT FROM` is not.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb
import psycopg

from ppd.config import Settings
from ppd.logging_utils import get_logger, log
from ppd.migrate import migrate

LOG = get_logger("ppd.postgres")

STAGING_COLS = [
    "transaction_id", "price", "sale_date", "postcode", "postcode_outward", "postcode_area",
    "property_type", "is_new_build", "tenure", "paon", "saon", "street", "locality",
    "town_city", "district", "county", "ppd_category", "load_seq",
]

ADDRESS_MATCH = """
        coalesce(p.postcode, '') = coalesce(s.postcode, '')
    and coalesce(p.paon, '')     = coalesce(s.paon, '')
    and coalesce(p.saon, '')     = coalesce(s.saon, '')
    and coalesce(p.street, '')   = coalesce(s.street, '')
    and p.district_id = d.district_id"""

UPSERTS = [
    ("county", """
        insert into ppd.county (name)
        select distinct county from staging.sale_load
        on conflict (name) do nothing"""),
    ("district", """
        insert into ppd.district (name, county_id)
        select distinct s.district, c.county_id
        from staging.sale_load s join ppd.county c on c.name = s.county
        on conflict (name, county_id) do nothing"""),
    ("town", """
        insert into ppd.town (name)
        select distinct town_city from staging.sale_load where town_city is not null
        on conflict (name) do nothing"""),
    ("postcode", """
        insert into ppd.postcode (postcode, outward_code, area)
        select distinct on (postcode) postcode, postcode_outward, postcode_area
        from staging.sale_load
        where postcode is not null
        on conflict (postcode) do nothing"""),
    ("property", """
        insert into ppd.property (postcode, paon, saon, street, locality, town_id, district_id)
        select distinct on (coalesce(s.postcode, ''), coalesce(s.paon, ''),
                            coalesce(s.saon, ''), coalesce(s.street, ''), d.district_id)
               s.postcode, s.paon, s.saon, s.street, s.locality, t.town_id, d.district_id
        from staging.sale_load s
        join ppd.county c    on c.name = s.county
        join ppd.district d  on d.name = s.district and d.county_id = c.county_id
        left join ppd.town t on t.name = s.town_city
        order by coalesce(s.postcode, ''), coalesce(s.paon, ''), coalesce(s.saon, ''),
                 coalesce(s.street, ''), d.district_id, s.load_seq desc
        on conflict on constraint property_address_uk do nothing"""),
    ("sale", f"""
        insert into ppd.sale (transaction_id, property_id, sale_date, price_gbp, property_type,
                              tenure, is_new_build, ppd_category, load_seq)
        select s.transaction_id, p.property_id, s.sale_date, s.price, s.property_type,
               coalesce(s.tenure, 'U'), s.is_new_build, s.ppd_category, s.load_seq
        from staging.sale_load s
        join ppd.county c   on c.name = s.county
        join ppd.district d on d.name = s.district and d.county_id = c.county_id
        join ppd.property p on {ADDRESS_MATCH}
        on conflict (transaction_id) do update
           set property_id = excluded.property_id, sale_date = excluded.sale_date,
               price_gbp = excluded.price_gbp, property_type = excluded.property_type,
               tenure = excluded.tenure, is_new_build = excluded.is_new_build,
               ppd_category = excluded.ppd_category, load_seq = excluded.load_seq,
               loaded_at = now()
         where ppd.sale.load_seq < excluded.load_seq"""),
    ("deleted_sales", """
        delete from ppd.sale t
        where not exists (select 1 from staging.sale_load s
                          where s.transaction_id = t.transaction_id)"""),
]


def export_silver_csv(settings: Settings, out: Path) -> int:
    glob = str(settings.path("silver") / "**" / "*.parquet")
    select_cols = ", ".join(
        "replace(replace(transaction_id, '{', ''), '}', '') as transaction_id"
        if c == "transaction_id"
        else "case when postcode_area is null then null else postcode end as postcode"
        if c == "postcode"
        else c
        for c in STAGING_COLS
    )
    con = duckdb.connect()
    con.execute(
        f"copy (select {select_cols} from read_parquet('{glob}', hive_partitioning = true)) "
        f"to '{out}' (header false)"
    )
    return con.execute(f"select count(*) from read_csv('{out}', header = false)").fetchone()[0]


def run(settings: Settings) -> dict[str, int]:
    dsn = os.environ.get("PPD_PG_DSN", settings.postgres_dsn)
    migrate(dsn)
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "silver.csv"
        counts: dict[str, int] = {"staged": export_silver_csv(settings, csv_path)}
        with psycopg.connect(dsn) as conn:
            with conn.transaction():
                conn.execute("truncate staging.sale_load")
                with conn.cursor() as cur, cur.copy(
                    f"copy staging.sale_load ({', '.join(STAGING_COLS)}) "
                    "from stdin with (format csv)"
                ) as copy, csv_path.open("rb") as fh:
                    while block := fh.read(1 << 20):
                        copy.write(block)
                conn.execute("analyze staging.sale_load")
                for name, sql in UPSERTS:
                    counts[name] = conn.execute(sql).rowcount
            conn.execute("analyze ppd.sale")
            counts["sales_total"] = conn.execute("select count(*) from ppd.sale").fetchone()[0]
    if counts["sales_total"] != counts["staged"]:
        raise RuntimeError(f"Postgres reconciliation failed: {counts}")
    log(LOG, "postgres load finished", **counts)
    return counts
