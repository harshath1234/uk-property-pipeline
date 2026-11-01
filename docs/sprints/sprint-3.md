# Sprint 3: dbt star schema

**Goal:** a tested dimensional model that runs on DuckDB now and BigQuery later.

Delivered
- `dbt/` project: source on silver Parquet → `stg_transactions` view →
  star schema (`fct_sales`, `dim_date`, `dim_location`, `dim_property`) →
  reporting marts (`rpt_monthly_prices`, `rpt_district_annual`).
- `fct_sales` is incremental: merges rows with a newer load sequence and a
  post-hook removes transactions deleted at source.
- Seeds for the published code lists (property type, tenure, PPD category).
- `macros/portable.sql`: surrogate keys, median, date spine and date keys
  written once per adapter so the models stay identical on both warehouses.
- Tests: unique / not null keys, accepted values, relationships from the fact
  to every dimension, a custom `positive_value` generic test, and a
  reconciliation test (fact rows = staging rows).

Checked on the synthetic fixture: a second monthly release with 5 deletes and
5 changes ran through the incremental path and the reconciliation test passed.

## Retro
- **Went well:** keeping adapter differences in four macros instead of
  scattered `if target.type` blocks.
- **Watch:** BigQuery's median is approximate (`APPROX_QUANTILES`), DuckDB's is
  exact. Medians can differ slightly between the two targets; documented in
  the data dictionary.
