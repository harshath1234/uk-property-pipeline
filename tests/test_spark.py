from __future__ import annotations

import csv

import pytest

from ppd import ingest
from ppd.spark_transform import build_bronze, build_silver, get_spark

pytestmark = pytest.mark.spark


@pytest.fixture(scope="module")
def spark():
    s = get_spark("ppd-tests")
    yield s
    s.stop()


def _rows(path):
    with open(path, newline="") as fh:
        return list(csv.reader(fh))


def test_silver_applies_monthly_changes(spark, settings, fixture_dir):
    ingest.run(settings, from_dir=fixture_dir)
    build_bronze(spark, settings)
    n = build_silver(spark, settings)

    monthly = _rows(fixture_dir / "pp-monthly-update-new-version.csv")
    adds = [r for r in monthly if r[15] == "A"]
    changes = {r[0]: int(r[1]) for r in monthly if r[15] == "C"}
    deletes = {r[0] for r in monthly if r[15] == "D"}
    yearly_rows = sum(len(_rows(fixture_dir / f"pp-{y}.csv")) for y in (2023, 2024, 2025))

    assert n == yearly_rows + len(adds) - len(deletes)

    silver = spark.read.parquet(str(settings.path("silver")))
    ids = {r.transaction_id for r in silver.select("transaction_id").collect()}
    assert not ids & deletes
    prices = {r.transaction_id: r.price
              for r in silver.filter(silver.transaction_id.isin(list(changes))).collect()}
    assert prices == changes
    assert silver.groupBy("transaction_id").count().filter("count > 1").count() == 0


def test_rerun_is_idempotent(spark, settings, fixture_dir):
    ingest.run(settings, from_dir=fixture_dir)
    build_bronze(spark, settings)
    first = build_silver(spark, settings)
    ingest.run(settings, from_dir=fixture_dir)
    build_bronze(spark, settings, force=True)
    assert build_silver(spark, settings) == first


def test_bad_rows_are_quarantined(spark, settings, fixture_dir, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    rows = _rows(fixture_dir / "pp-2024.csv")
    rows[0][1] = "not-a-price"
    with open(src / "pp-2024.csv", "w", newline="") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)
    ingest.run(settings, from_dir=src)
    written = build_bronze(spark, settings)
    assert written["pp-2024.csv"] == len(rows) - 1
    assert (settings.path("data_root") / "quarantine").exists()


def test_monthly_rows_for_unloaded_years_are_dropped(spark, settings, fixture_dir, tmp_path):
    """The real monthly file carries late registrations back to 1995. Years
    with no yearly snapshot must not leak into silver as tiny partitions."""
    src = tmp_path / "src"
    src.mkdir()
    for y in (2023, 2024, 2025):
        (src / f"pp-{y}.csv").write_bytes((fixture_dir / f"pp-{y}.csv").read_bytes())
    monthly = _rows(fixture_dir / "pp-monthly-update-new-version.csv")
    old = list(monthly[0])
    old[0] = "{11111111-2222-3333-4444-555555555555}"
    old[2] = "1996-05-01 00:00"
    old[15] = "A"
    with open(src / "pp-monthly-update-new-version.csv", "w", newline="") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows([*monthly, old])

    ingest.run(settings, from_dir=src)
    build_bronze(spark, settings)
    build_silver(spark, settings)
    silver = spark.read.parquet(str(settings.path("silver")))
    years = {r.sale_year for r in silver.select("sale_year").distinct().collect()}
    assert years == {2023, 2024, 2025}
