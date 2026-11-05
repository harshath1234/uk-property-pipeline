"""Export dashboard data from the reporting marts to site/data/*.json.

Every number on the dashboard comes from these files, and these files come
only from the warehouse built by the last pipeline run. If that run used the
synthetic test fixture, the export is labelled as such and the dashboard
shows a warning banner.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from ppd.config import Settings
from ppd.ingest import Manifest
from ppd.logging_utils import get_logger, log

LOG = get_logger("ppd.site")

QUERIES = {
    "monthly": """
        select cast(month_start as date) as month, property_type, sales,
               median_price_gbp, round(mean_price_gbp) as mean_price_gbp
        from {reporting}.rpt_monthly_prices order by month, property_type""",
    "districts": """
        select district, county, year, sales, median_price_gbp,
               round(median_yoy_change, 4) as median_yoy_change, price_rank_in_year
        from {reporting}.rpt_district_annual
        order by year, district""",
    "kpis": """
        select count(*) as sales,
               min(d.date_day) as first_sale, max(d.date_day) as last_sale,
               count(distinct f.location_key) as districts
        from {marts}.fct_sales f join {marts}.dim_date d on d.date_key = f.date_key""",
    "by_type": """
        select p.property_type, count(*) as sales
        from {marts}.fct_sales f join {marts}.dim_property p on p.property_key = f.property_key
        group by 1 order by 2 desc""",
    # ---- extra cuts for the dashboard (category A = standard-price sales)
    "yearly": """
        select d.year,
               count(*)                                                    as sales,
               {med_price}                                                 as median_price_gbp,
               sum(case when p.is_new_build then 1 else 0 end)             as new_build_sales,
               sum(case when p.tenure_code = 'L' then 1 else 0 end)        as leasehold_sales,
               {med_new}                                                   as median_new_build_gbp,
               {med_old}                                                   as median_established_gbp
        from {marts}.fct_sales f
        join {marts}.dim_date d     on d.date_key = f.date_key
        join {marts}.dim_property p on p.property_key = f.property_key
        where f.ppd_category_code = 'A'
        group by d.year order by d.year""",
    "type_year": """
        select d.year, p.property_type, count(*) as sales, {med_price} as median_price_gbp
        from {marts}.fct_sales f
        join {marts}.dim_date d     on d.date_key = f.date_key
        join {marts}.dim_property p on p.property_key = f.property_key
        where f.ppd_category_code = 'A'
        group by d.year, p.property_type order by d.year, p.property_type""",
    "monthly_volume": """
        select cast(d.month_start as date) as month, count(*) as sales,
               sum(case when f.ppd_category_code = 'B' then 1 else 0 end) as category_b_sales
        from {marts}.fct_sales f join {marts}.dim_date d on d.date_key = f.date_key
        group by d.month_start order by d.month_start""",
    "county_year": """
        select l.county, d.year, count(*) as sales, {med_price} as median_price_gbp
        from {marts}.fct_sales f
        join {marts}.dim_date d     on d.date_key = f.date_key
        join {marts}.dim_location l on l.location_key = f.location_key
        where f.ppd_category_code = 'A'
        group by l.county, d.year order by l.county, d.year""",
    "price_bands": """
        select d.year,
               case when f.price_gbp < 100000 then 1 when f.price_gbp < 200000 then 2
                    when f.price_gbp < 300000 then 3 when f.price_gbp < 400000 then 4
                    when f.price_gbp < 500000 then 5 when f.price_gbp < 750000 then 6
                    when f.price_gbp < 1000000 then 7 else 8 end as band,
               count(*) as sales
        from {marts}.fct_sales f join {marts}.dim_date d on d.date_key = f.date_key
        where f.ppd_category_code = 'A'
        group by 1, 2 order by 1, 2""",
    "postcode_areas": """
        select f.postcode_area, d.year, count(*) as sales, {med_price} as median_price_gbp
        from {marts}.fct_sales f join {marts}.dim_date d on d.date_key = f.date_key
        where f.ppd_category_code = 'A' and f.postcode_area is not null
        group by f.postcode_area, d.year order by f.postcode_area, d.year""",
}


def _median(expr: str, bigquery: bool) -> str:
    """Median that works on both warehouses (NULLs ignored)."""
    if bigquery:
        return f"approx_quantiles({expr}, 100 ignore nulls)[offset(50)]"
    return f"median({expr})"


def _names(bigquery: bool, reporting: str, marts: str) -> dict[str, str]:
    return {
        "reporting": reporting,
        "marts": marts,
        "med_price": _median("f.price_gbp", bigquery),
        "med_new": _median("case when p.is_new_build then f.price_gbp end", bigquery),
        "med_old": _median("case when not p.is_new_build then f.price_gbp end", bigquery),
    }


def _fetch(settings: Settings) -> dict[str, list[dict]]:
    target = os.environ.get("PPD_DBT_TARGET", settings.raw["warehouse"]["target"])
    out: dict[str, list[dict]] = {}
    if target == "bigquery":
        from google.cloud import bigquery

        project = os.environ["PPD_GCP_PROJECT"]
        client = bigquery.Client(project=project)
        names = _names(True, f"`{project}.reporting`", f"`{project}.marts`")
        for key, sql in QUERIES.items():
            out[key] = [dict(r) for r in client.query(sql.format(**names)).result()]
    else:
        import duckdb

        con = duckdb.connect(str(settings.path("warehouse")), read_only=True)
        for key, sql in QUERIES.items():
            cur = con.execute(sql.format(**_names(False, "reporting", "marts")))
            cols = [c[0] for c in cur.description]
            out[key] = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return out


def _run_metadata(settings: Settings) -> dict:
    manifest = Manifest(settings.path("manifest"))
    synthetic = any("tests/fixtures" in e.source.replace("\\", "/") for e in manifest.entries)
    reports = settings.path("data_root") / "reports"
    def read(name: str):
        path = reports / name
        return json.loads(path.read_text()) if path.exists() else None

    quality = read("quality.json")
    raw = read("raw_validation.json")
    dbt = read("dbt_run_results.json")
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "synthetic_fixture": synthetic,
        "dataset_label": ("SYNTHETIC TEST FIXTURE - not real data" if synthetic
                          else "HM Land Registry Price Paid Data"),
        "source_files": [
            {"name": e.name, "kind": e.kind, "bytes": e.bytes, "sha256": e.sha256[:12],
             "landed_at": e.landed_at}
            for e in sorted(manifest.entries, key=lambda e: e.load_seq)
        ],
        "quality": None if quality is None else {
            "success": quality["success"],
            "partitions": len(quality["partitions"]),
            "rows_validated": sum(p["rows"] for p in quality["partitions"].values()),
            "expectations_per_partition": max(
                (p["evaluated"] for p in quality["partitions"].values()), default=0),
        },
        "raw_validation": None if raw is None else {
            "files": len(raw),
            "rows": sum(r["rows"] for r in raw),
            "failing_rows": sum(r["failing_rows"] for r in raw),
        },
        "dbt": None if dbt is None else {
            "models": sum(1 for r in dbt["results"]
                          if r["unique_id"].startswith("model.") and r["status"] == "success"),
            "tests_passed": sum(1 for r in dbt["results"]
                                if r["unique_id"].startswith("test.") and r["status"] == "pass"),
            "tests_total": sum(1 for r in dbt["results"] if r["unique_id"].startswith("test.")),
        },
    }


def run(settings: Settings, out_dir: Path | None = None) -> Path:
    out = out_dir or settings.root / "site" / "data"
    out.mkdir(parents=True, exist_ok=True)
    data = _fetch(settings)
    payload = {"meta": _run_metadata(settings), **data}
    (out / "dashboard.json").write_text(json.dumps(payload, indent=1, default=str))
    log(LOG, "site data exported", path=str(out / "dashboard.json"),
        synthetic=payload["meta"]["synthetic_fixture"], sales=data["kpis"][0]["sales"])
    return out / "dashboard.json"
