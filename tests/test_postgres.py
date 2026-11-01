"""Integration tests against a real PostgreSQL (CI starts one as a service).
Skipped when PPD_PG_DSN is not set."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.postgres, pytest.mark.spark]
DSN = os.environ.get("PPD_PG_DSN")
if not DSN:
    pytest.skip("PPD_PG_DSN not set", allow_module_level=True)

import psycopg  # noqa: E402

from ppd import ingest  # noqa: E402
from ppd.load_postgres import run as load_pg  # noqa: E402
from ppd.migrate import discover, migrate  # noqa: E402
from ppd.spark_transform import run as spark_run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def clean_db():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("drop schema if exists ppd cascade")
        conn.execute("drop schema if exists staging cascade")
        conn.execute("drop schema if exists ppd_meta cascade")
    yield DSN


def test_migrations_apply_once(clean_db):
    applied = migrate(clean_db)
    assert applied == [v for v, _, _ in discover()]
    assert migrate(clean_db) == []


def test_edited_migration_is_refused(clean_db, tmp_path):
    for _, _, f in discover():
        (tmp_path / f.name).write_text(f.read_text())
    migrate(clean_db, tmp_path)
    first = sorted(tmp_path.glob("V001*"))[0]
    first.write_text(first.read_text() + "\n-- sneaky edit\n")
    with pytest.raises(RuntimeError, match="edited after being applied"):
        migrate(clean_db, tmp_path)


def test_load_is_idempotent_and_queries_run(clean_db, settings, fixture_dir):
    ingest.run(settings, from_dir=fixture_dir)
    silver_rows = spark_run(settings)
    first = load_pg(settings)
    assert first["sales_total"] == silver_rows
    second = load_pg(settings)
    assert second["sales_total"] == silver_rows
    assert second["sale"] == 0 and second["property"] == 0

    with psycopg.connect(clean_db) as conn:
        for q in sorted((ROOT / "sql" / "queries").glob("*.sql")):
            conn.execute(q.read_text())  # every query in the pack must run
