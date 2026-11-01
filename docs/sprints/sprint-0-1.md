# Sprints 0 and 1: foundations and ingestion

## Sprint 0: foundations
**Goal:** a repo a reviewer can clone, read and run tests on.

Delivered
- Repo layout, MIT licence, `pyproject.toml`, config file with env overrides.
- JSON-lines logging (`src/ppd/logging_utils.py`).
- CI workflow: ruff lint, pytest, end-to-end fixture run, Docker build.
- Backlog and ADRs 0001 (architecture) and 0002 (incremental loads).

## Sprint 1: idempotent ingestion and raw validation
**Goal:** land every source file safely, once, and stop bad files early.

Delivered
- `src/ppd/ingest.py`: HEAD check on ETag/size, streaming download to a temp
  file then atomic rename, SHA-256 manifest with load sequence numbers,
  retries with exponential backoff, offline `--from-dir` mode.
- `src/ppd/schema.py`: the published 16-column layout and a pandera schema
  (GUID format, positive price, code lists, postcode pattern). Files are
  validated chunk by chunk and fail above a 0.1% bad-row rate.
- Tests: idempotent re-run, unchanged remote skipped, transient errors
  retried, bad codes and wrong column count rejected.

## Retro
- **Went well:** testing download logic with fake HTTP responses kept tests
  fast and offline.
- **Learned:** the monthly change file reuses one URL every month, so the URL
  can't be the identity of a release. Content hash is.
- **Change for next sprint:** decide how yearly snapshots and monthly changes
  combine before writing Spark code (now in ADR 0002).
