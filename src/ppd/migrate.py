"""Minimal versioned-migration runner (the idea behind Flyway / Alembic).

- Files are named V<number>__<description>.sql and applied in number order.
- Each runs in its own transaction and is recorded in ppd_meta.schema_migrations
  with a SHA-256 checksum.
- Editing a migration that has already been applied is refused: schema
  changes go in a new file.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import psycopg

from ppd.config import PROJECT_ROOT
from ppd.logging_utils import get_logger, log

LOG = get_logger("ppd.migrate")
MIGRATIONS_DIR = PROJECT_ROOT / "postgres" / "migrations"
NAME_RE = re.compile(r"^V(\d+)__([a-z0-9_]+)\.sql$")


def discover(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, str, Path]]:
    found = []
    for f in directory.glob("*.sql"):
        m = NAME_RE.match(f.name)
        if not m:
            raise ValueError(f"Badly named migration: {f.name}")
        found.append((int(m.group(1)), m.group(2), f))
    found.sort()
    versions = [v for v, _, _ in found]
    if len(versions) != len(set(versions)):
        raise ValueError("Duplicate migration version numbers")
    return found


def migrate(dsn: str, directory: Path = MIGRATIONS_DIR) -> list[int]:
    applied_now: list[int] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("create schema if not exists ppd_meta")
        conn.execute(
            """create table if not exists ppd_meta.schema_migrations (
                   version integer primary key, name text not null,
                   checksum text not null, applied_at timestamptz not null default now())"""
        )
        done = dict(conn.execute(
            "select version, checksum from ppd_meta.schema_migrations").fetchall())
        for version, name, path in discover(directory):
            sql = path.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if version in done:
                if done[version] != checksum:
                    raise RuntimeError(
                        f"Migration V{version} was edited after being applied. "
                        "Add a new migration instead.")
                continue
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "insert into ppd_meta.schema_migrations (version, name, checksum) "
                    "values (%s, %s, %s)", (version, name, checksum))
            applied_now.append(version)
            log(LOG, "migration applied", version=version, name=name)
    return applied_now
