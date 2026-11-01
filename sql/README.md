# SQL query pack (PostgreSQL)

Analytical queries over the normalised model in `postgres/migrations/`.
Each file says which techniques it uses.

| File | Question | Techniques |
|---|---|---|
| `01_repeat_sales_growth.sql` | How fast do prices grow for homes sold twice? | CTEs, `LAG` over a named window, `power()` annualisation, `percentile_cont` |
| `02_district_rank_and_yoy.sql` | Top 10 districts by median price each year, with YoY change | ordered-set aggregate, `LAG`, `DENSE_RANK`, `HAVING` |
| `03_new_build_premium.sql` | How much more do new builds sell for? | `FILTER` on aggregates, `NULLIF` guard |
| `04_rising_streaks.sql` | Longest run of month-on-month median rises per district | gaps-and-islands (`ROW_NUMBER` difference) |
| `05_rolling_volume.sql` | Monthly volume, 12-month rolling total, leasehold share | `ROWS BETWEEN` frame, `FILTER`, BRIN-friendly date filter |

## Query plans
`python scripts/explain_queries.py` runs each query with
`EXPLAIN (ANALYZE, BUFFERS)` and writes the plan to `sql/plans/`. Plans are
only committed from runs on the real dataset.

## Indexing choices (see `V002`, `V003`)
- `sale_property_date_idx (property_id, sale_date)`: lets query 01's window
  read each property's sales already in order instead of sorting ~10M rows.
- `sale_date_brin`: sales are loaded roughly in date order, so a BRIN index
  is a few hundred KB yet still prunes date-range scans (query 05). A B-tree
  on the same column would be hundreds of MB.
- `property_address_match_idx`: an expression index on the null-safe
  `coalesce(...)` keys the loader joins on.

What to check in the plans after a real run:
1. Does query 01 use `sale_property_date_idx` or a full `Sort`? Compare with
   the index dropped (`drop index ppd.sale_property_date_idx;` then re-run).
2. Does query 05 show a `Bitmap Index Scan on sale_date_brin`? If the date
   range covers almost all rows, a sequential scan is the right choice and
   the planner will say so.
3. Look for `Sort Method: external merge Disk:` lines, which mean `work_mem`
   is too small for that sort.
