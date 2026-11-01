"""Great Expectations suite for the silver layer.

The suite is defined in code (so it is reviewed and versioned like any other
code) and run one sale-year partition at a time, which keeps memory flat on a
laptop however many years are loaded. Results go to data/reports/quality.json
and GE's HTML Data Docs are built under data/gx/.

Cross-partition rules (transaction_id unique across all years) are enforced
in dbt, which sees the whole table.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import duckdb
import great_expectations as gx
import great_expectations.expectations as gxe

from ppd.config import Settings
from ppd.logging_utils import get_logger, log
from ppd.schema import GUID_PATTERN, POSTCODE_PATTERN

os.environ.setdefault("TQDM_DISABLE", "1")  # quiet GE progress bars in logs
LOG = get_logger("ppd.quality")
SUITE_NAME = "silver_transactions"

COLUMNS = [
    "transaction_id", "price", "sale_date", "postcode", "property_type", "tenure",
    "ppd_category", "district", "county", "is_new_build",
]


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name=SUITE_NAME)
    for e in [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectTableColumnsToMatchSet(column_set=COLUMNS, exact_match=True),
        gxe.ExpectColumnValuesToNotBeNull(column="transaction_id"),
        gxe.ExpectColumnValuesToBeUnique(column="transaction_id"),
        gxe.ExpectColumnValuesToMatchRegex(column="transaction_id", regex=GUID_PATTERN),
        gxe.ExpectColumnValuesToNotBeNull(column="price"),
        gxe.ExpectColumnValuesToBeBetween(column="price", min_value=1),
        # Most sales sit in this band; a shift would point to a unit or parsing bug.
        gxe.ExpectColumnValuesToBeBetween(
            column="price", min_value=10_000, max_value=5_000_000, mostly=0.97),
        gxe.ExpectColumnMedianToBeBetween(column="price", min_value=100_000, max_value=800_000),
        gxe.ExpectColumnValuesToNotBeNull(column="sale_date"),
        gxe.ExpectColumnValuesToBeBetween(
            column="sale_date", min_value=datetime(1995, 1, 1), max_value=datetime.now()),
        gxe.ExpectColumnValuesToBeInSet(
            column="property_type", value_set=["D", "S", "T", "F", "O"]),
        gxe.ExpectColumnValuesToBeInSet(column="tenure", value_set=["F", "L", "U"]),
        gxe.ExpectColumnValuesToBeInSet(column="ppd_category", value_set=["A", "B"]),
        gxe.ExpectColumnValuesToMatchRegex(column="postcode", regex=POSTCODE_PATTERN, mostly=0.99),
        gxe.ExpectColumnValuesToNotBeNull(column="district"),
        gxe.ExpectColumnValuesToNotBeNull(column="county"),
    ]:
        suite.add_expectation(e)
    return suite


def run(settings: Settings) -> dict:
    root = settings.path("data_root")
    context = gx.get_context(mode="file", project_root_dir=str(root))
    try:  # progress bars make JSON logs unreadable
        from great_expectations.data_context.types.base import ProgressBarsConfig

        context.variables.progress_bars = ProgressBarsConfig(globally=False)
    except (ImportError, AttributeError):
        pass
    datasource = context.data_sources.add_or_update_pandas(name="silver")
    try:
        asset = datasource.get_asset("silver_transactions")
    except LookupError:
        asset = datasource.add_dataframe_asset(name="silver_transactions")
    try:
        batch_def = asset.get_batch_definition("partition")
    except (KeyError, LookupError):
        batch_def = asset.add_batch_definition_whole_dataframe("partition")
    suite = context.suites.add_or_update(build_suite())
    validation = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(name="silver_partition", data=batch_def, suite=suite)
    )

    glob = str(settings.path("silver") / "**" / "*.parquet")
    con = duckdb.connect()
    years = [r[0] for r in con.execute(
        f"select distinct sale_year from read_parquet('{glob}', hive_partitioning = true) "
        "order by 1").fetchall()]

    summary: dict = {"suite": SUITE_NAME, "partitions": {}, "success": True}
    for year in years:
        df = con.execute(
            f"select {', '.join(COLUMNS)} from read_parquet('{glob}', hive_partitioning = true) "
            f"where sale_year = {int(year)}").df()
        df["sale_date"] = df["sale_date"].astype("datetime64[ns]")
        result = validation.run(batch_parameters={"dataframe": df})
        failed = [
            {"expectation": r.expectation_config.type,
             "column": r.expectation_config.kwargs.get("column"),
             "unexpected_percent": r.result.get("unexpected_percent")}
            for r in result.results if not r.success
        ]
        summary["partitions"][str(year)] = {
            "rows": len(df), "evaluated": len(result.results),
            "success": result.success, "failed": failed,
        }
        summary["success"] &= result.success
        log(LOG, "partition validated", year=int(year), rows=len(df), success=result.success,
            failed=len(failed))

    try:
        context.build_data_docs()
    except Exception as exc:  # noqa: BLE001 - docs are a nice-to-have, not a gate
        log(LOG, "data docs not built", error=str(exc))

    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "quality.json").write_text(json.dumps(summary, indent=2, default=str))
    if not summary["success"]:
        raise RuntimeError(f"Great Expectations checks failed: {json.dumps(summary)[:2000]}")
    return summary
