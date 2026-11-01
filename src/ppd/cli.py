"""Command line entry point: `ppd <stage>` or `ppd run-all`.

Stages, in order:
  ingest      download (or copy with --from-dir) source files into landing
  validate    pandera checks on every landed file
  transform   Spark: landing -> bronze -> silver
  quality     Great Expectations suite on silver
  bigquery    load silver into BigQuery (only when the target is bigquery)
  dbt         dbt seed + build (models and tests) on the configured target
  postgres    apply migrations and load the normalised PostgreSQL model
  site        export dashboard data from the marts into site/data/
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ppd.config import PROJECT_ROOT, Settings, load_settings
from ppd.logging_utils import get_logger, log

LOG = get_logger("ppd.cli")


def _reports_dir(settings: Settings) -> Path:
    d = settings.path("data_root") / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_ingest(settings: Settings, from_dir: str | None = None) -> None:
    from ppd import ingest

    results = ingest.run(settings, Path(from_dir) if from_dir else None)
    log(LOG, "ingest finished", results=results)


def stage_validate(settings: Settings) -> None:
    from ppd.ingest import Manifest
    from ppd.schema import validate_file

    reports = []
    for entry in Manifest(settings.path("manifest")).entries:
        reports.append(validate_file(settings.path("landing") / entry.name))
    (_reports_dir(settings) / "raw_validation.json").write_text(json.dumps(reports, indent=2))
    log(LOG, "raw validation passed", files=len(reports),
        rows=sum(r["rows"] for r in reports))


def stage_transform(settings: Settings) -> None:
    from ppd import spark_transform

    spark_transform.run(settings)


def stage_quality(settings: Settings) -> None:
    from ppd import quality

    quality.run(settings)


def stage_bigquery(settings: Settings) -> None:
    """Load silver into BigQuery. No-op unless the warehouse target is bigquery."""
    if os.environ.get("PPD_DBT_TARGET", settings.raw["warehouse"]["target"]) != "bigquery":
        log(LOG, "warehouse target is not bigquery; skipping load")
        return
    from ppd import cloud

    cloud.load_silver_to_bigquery(settings)


def dbt_env(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PPD_DBT_TARGET", settings.raw["warehouse"]["target"])
    env["PPD_SILVER_GLOB"] = str(settings.path("silver") / "**" / "*.parquet")
    env["PPD_DUCKDB_PATH"] = str(settings.path("warehouse"))
    return env


def stage_dbt(settings: Settings, args: list[str] | None = None) -> None:
    dbt_dir = PROJECT_ROOT / "dbt"
    base = ["dbt", "--no-use-colors"]
    common = ["--project-dir", str(dbt_dir), "--profiles-dir", str(dbt_dir)]
    extra = list(args or [])
    if os.environ.get("PPD_BQ_SANDBOX", "").lower() in {"1", "true", "yes"}:
        extra += ["--vars", "{incremental: false}"]  # sandbox has no MERGE/DELETE
    for cmd in (["seed"], ["build", *extra]):
        log(LOG, "dbt", command=" ".join(cmd))
        subprocess.run([*base, *cmd, *common], check=True, env=dbt_env(settings))
    results = dbt_dir / "target" / "run_results.json"
    if results.exists():  # keep test results with the run's other reports
        shutil.copyfile(results, _reports_dir(settings) / "dbt_run_results.json")


def stage_postgres(settings: Settings) -> None:
    from ppd import load_postgres

    load_postgres.run(settings)


def stage_site(settings: Settings) -> None:
    from ppd import export_site

    export_site.run(settings)


def stage_ons(settings: Settings, path: str, sheet: str | None) -> None:
    """Parse an ONS HPSSA workbook and reconcile it with the warehouse medians."""
    from ppd import ons_excel

    df = ons_excel.parse_workbook(Path(path), sheet_hint=sheet)
    out = settings.path("data_root") / "external"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "ons_hpssa.parquet", index=False)
    rec = ons_excel.reconcile_with_warehouse(df, settings.path("warehouse"))
    rec.to_csv(_reports_dir(settings) / "ons_reconciliation.csv", index=False)
    log(LOG, "ons reconciliation", matched_district_years=len(rec),
        median_abs_pct_diff=None if rec.empty else round(float(rec["pct_diff"].abs().median()), 4))


STAGES = {
    "ingest": stage_ingest,
    "validate": stage_validate,
    "transform": stage_transform,
    "quality": stage_quality,
    "bigquery": stage_bigquery,
    "dbt": stage_dbt,
    "postgres": stage_postgres,
    "site": stage_site,
}
DEFAULT_RUN = [
    "ingest", "validate", "transform", "quality", "bigquery", "dbt", "postgres", "site",
]


def run_all(settings: Settings, from_dir: str | None, skip: list[str]) -> None:
    timings = {}
    for name in DEFAULT_RUN:
        if name in skip:
            log(LOG, "stage skipped", stage=name)
            continue
        t0 = time.time()
        if name == "ingest":
            stage_ingest(settings, from_dir)
        else:
            STAGES[name](settings)
        timings[name] = round(time.time() - t0, 1)
        log(LOG, "stage done", stage=name, seconds=timings[name])
    (_reports_dir(settings) / "run_timings.json").write_text(json.dumps(timings, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ppd", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="path to pipeline.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--from-dir", help="copy local files instead of downloading")
    for name in ("validate", "transform", "quality", "bigquery", "postgres", "site"):
        sub.add_parser(name)
    p_dbt = sub.add_parser("dbt")
    p_dbt.add_argument("dbt_args", nargs=argparse.REMAINDER)
    p_ons = sub.add_parser("ons", help="parse an ONS house-price workbook and reconcile")
    p_ons.add_argument("path")
    p_ons.add_argument("--sheet", help="substring of the sheet name, e.g. 2a")
    p_all = sub.add_parser("run-all")
    p_all.add_argument("--from-dir")
    p_all.add_argument("--skip", default="", help="comma-separated stages to skip")

    a = parser.parse_args(argv)
    settings = load_settings(Path(a.config) if a.config else None)
    try:
        if a.cmd == "ingest":
            stage_ingest(settings, a.from_dir)
        elif a.cmd == "dbt":
            stage_dbt(settings, a.dbt_args)
        elif a.cmd == "ons":
            stage_ons(settings, a.path, a.sheet)
        elif a.cmd == "run-all":
            run_all(settings, a.from_dir, [s for s in a.skip.split(",") if s])
        else:
            STAGES[a.cmd](settings)
    except Exception as exc:  # noqa: BLE001 - top-level: log and exit non-zero
        LOG.exception("stage failed", extra={"fields": {"cmd": a.cmd, "error": str(exc)}})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
