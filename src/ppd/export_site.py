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
}


def _fetch(settings: Settings) -> dict[str, list[dict]]:
    target = os.environ.get("PPD_DBT_TARGET", settings.raw["warehouse"]["target"])
    out: dict[str, list[dict]] = {}
    if target == "bigquery":
        from google.cloud import bigquery

        project = os.environ["PPD_GCP_PROJECT"]
        client = bigquery.Client(project=project)
        names = {"reporting": f"`{project}.reporting`", "marts": f"`{project}.marts`"}
        for key, sql in QUERIES.items():
            out[key] = [dict(r) for r in client.query(sql.format(**names)).result()]
    else:
        import duckdb

        con = duckdb.connect(str(settings.path("warehouse")), read_only=True)
        for key, sql in QUERIES.items():
            cur = con.execute(sql.format(reporting="reporting", marts="marts"))
            cols = [c[0] for c in cur.description]
            out[key] = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return out


def _run_metadata(settings: Settings) -> dict:
    manifest = Manifest(settings.path("manifest"))
    synthetic = any("tests/fixtures" in e.source.replace("\\", "/") for e in manifest.entries)
    reports = settings.path("data_root") / "reports"
    quality = json.loads((reports / "quality.json").read_text()) \
        if (reports / "quality.json").exists() else None
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
