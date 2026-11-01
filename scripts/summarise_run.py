"""Collect the figures from the last real run into reports/results.json.

Every number in the README results section, the portfolio card and the CV
must be copied from this file, never typed from memory.

Usage: python scripts/summarise_run.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb

from ppd.config import load_settings
from ppd.ingest import Manifest


def main() -> None:
    s = load_settings()
    data = s.path("data_root")
    reports = data / "reports"
    manifest = Manifest(s.path("manifest"))
    silver_glob = str(s.path("silver") / "**" / "*.parquet")

    con = duckdb.connect(str(s.path("warehouse")), read_only=True)
    q = lambda sql: con.execute(sql).fetchone()  # noqa: E731

    raw = json.loads((reports / "raw_validation.json").read_text())
    quality = json.loads((reports / "quality.json").read_text())
    timings = json.loads((reports / "run_timings.json").read_text()) \
        if (reports / "run_timings.json").exists() else {}
    quarantine = data / "quarantine"

    results = {
        "synthetic_fixture": any("tests/fixtures" in e.source for e in manifest.entries),
        "source_files": len(manifest.entries),
        "source_bytes": sum(e.bytes for e in manifest.entries),
        "raw_rows": sum(r["rows"] for r in raw),
        "raw_failing_rows": sum(r["failing_rows"] for r in raw),
        "quarantined_files": len(list(quarantine.rglob("*.parquet"))) if quarantine.exists() else 0,
        "silver_rows": q(f"select count(*) from read_parquet('{silver_glob}')")[0],
        "fact_rows": q("select count(*) from marts.fct_sales")[0],
        "sale_date_range": [str(x) for x in q(
            "select min(date_day), max(date_day) from marts.dim_date")],
        "districts": q("select count(*) from marts.dim_location")[0],
        "ge_partitions": len(quality["partitions"]),
        "ge_expectations_per_partition": max(
            p["evaluated"] for p in quality["partitions"].values()),
        "ge_success": quality["success"],
        "stage_seconds": timings,
    }
    manifest_path = reports / "dbt_run_results.json"
    if manifest_path.exists():
        rr = json.loads(manifest_path.read_text())["results"]
        results["dbt_tests_passed"] = sum(
            1 for r in rr if r["unique_id"].startswith("test.") and r["status"] == "pass")
        results["dbt_models_built"] = sum(
            1 for r in rr if r["unique_id"].startswith("model.") and r["status"] == "success")
    dsn = os.environ.get("PPD_PG_DSN", s.postgres_dsn)
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=3) as pg:
            for t in ("sale", "property", "postcode", "district"):
                results[f"postgres_{t}_rows"] = pg.execute(
                    f"select count(*) from ppd.{t}").fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        results["postgres"] = f"not reachable: {exc.__class__.__name__}"

    out = Path(os.environ.get("PPD_PROJECT_ROOT", ".")) / "reports"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))
    if results["synthetic_fixture"]:
        print("\nWARNING: this run used the synthetic fixture. Do not quote these numbers.")


if __name__ == "__main__":
    main()
