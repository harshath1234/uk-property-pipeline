# Common tasks. `make help` lists them.
SHELL := /bin/bash
PY ?= python

.PHONY: help install fixtures test lint e2e-fixture run run-fixture up up-fixture airflow \
        explain site-preview gcp-load clean

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:         ## install the package with every extra used locally
	$(PY) -m pip install -e ".[dev,dbt,quality,ons]"

fixtures:        ## regenerate the synthetic test files
	$(PY) tests/fixtures/make_fixtures.py tests/fixtures/ppd

lint:            ## ruff
	ruff check src tests airflow scripts

test:            ## unit + integration tests (Postgres tests need PPD_PG_DSN)
	pytest

e2e-fixture:     ## whole pipeline on the synthetic fixture, in .e2e/ (used by CI)
	rm -rf .e2e && mkdir -p .e2e
	PPD_ROOT=$(CURDIR)/.e2e ppd run-all --from-dir tests/fixtures/ppd \
	  $(if $(PPD_PG_DSN),,--skip postgres)
	$(PY) -c "import json; d=json.load(open('.e2e/site/data/dashboard.json')); \
	  assert d['meta']['synthetic_fixture'] and d['kpis'][0]['sales'] > 0; print('e2e ok')"

run:             ## REAL run on your machine: download, Spark, GE, dbt, Postgres, site
	ppd run-all

up:              ## same as `run`, inside Docker (one command, nothing to install)
	docker compose up --build --abort-on-container-exit pipeline

up-fixture:      ## Docker demo on the synthetic fixture (no download)
	PPD_RUN_ARGS="--from-dir tests/fixtures/ppd" docker compose up --build --abort-on-container-exit pipeline

airflow:         ## Airflow UI on http://localhost:8080
	docker compose --profile airflow up --build

explain:         ## save EXPLAIN ANALYZE plans for sql/queries into sql/plans
	$(PY) scripts/explain_queries.py

site-preview:    ## serve the dashboard on http://localhost:8000
	cd site && $(PY) -m http.server 8000

gcp-load:        ## load silver to BigQuery and build dbt there (see docs/cloud.md)
	PPD_DBT_TARGET=bigquery ppd bigquery && PPD_DBT_TARGET=bigquery ppd dbt

clean:           ## remove generated data (keeps downloads in data/landing)
	rm -rf data/bronze data/silver data/warehouse.duckdb data/quarantine data/reports .e2e dbt/target
