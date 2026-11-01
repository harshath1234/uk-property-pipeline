"""Run every query in sql/queries with EXPLAIN (ANALYZE, BUFFERS) and save the
plans to sql/plans/. Run this on the real data, then commit the plans: they are
the evidence for the query-tuning notes in sql/README.md.

Usage: python scripts/explain_queries.py [--dsn postgresql://...]
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get(
        "PPD_PG_DSN", "postgresql://ppd:ppd@localhost:5432/ppd"))
    args = ap.parse_args()
    out_dir = ROOT / "sql" / "plans"
    out_dir.mkdir(exist_ok=True)
    with psycopg.connect(args.dsn) as conn:
        version = conn.execute("show server_version").fetchone()[0]
        n = conn.execute("select count(*) from ppd.sale").fetchone()[0]
        for q in sorted((ROOT / "sql" / "queries").glob("*.sql")):
            sql = q.read_text().strip().rstrip(";")
            t0 = time.time()
            plan = conn.execute(f"explain (analyze, buffers, format text) {sql}").fetchall()
            took = time.time() - t0
            header = (f"-- {q.name} | PostgreSQL {version} | ppd.sale rows: {n:,} | "
                      f"wall time {took:.2f}s\n")
            (out_dir / f"{q.stem}.txt").write_text(header + "\n".join(r[0] for r in plan) + "\n")
            print(f"{q.name}: {took:.2f}s")


if __name__ == "__main__":
    main()
