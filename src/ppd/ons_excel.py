"""Parse ONS house-price workbooks whose layout changes between releases.

Target: ONS "House price statistics for small areas" (HPSSA) tables, e.g.
dataset 9 (median price paid by local authority, year ending each quarter).
Download the workbook from ons.gov.uk into data/external/ by hand.

Things that vary between releases, and how each is handled:
- title and notes rows above the table   -> header row is *found*, not assumed
- header wording ("Local authority code" vs "LA code" vs "Area code")
                                         -> matched with patterns, not exact text
- sheet names and order                  -> the sheet is picked by a hint or by
                                            looking for a header row
- period headers ("Year ending Mar 2024", "Mar-2024", datetime cells)
                                         -> all parsed to a month-end date
- suppressed values (":", "[x]", "[c]", "..") and thousands separators
                                         -> NULL / number
- .xlsx and legacy .xls                  -> openpyxl / xlrd via pandas

Output is long format: area_code, area_name, period_end, value.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from ppd.logging_utils import get_logger, log

LOG = get_logger("ppd.ons")

CODE_PATTERNS = [r"local authority code", r"\bla code\b", r"area code", r"^code$"]
NAME_PATTERNS = [r"local authority name", r"\bla name\b", r"area name", r"^name$"]
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
PERIOD_RE = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_/]*(\d{4})",
                       re.I)
SUPPRESSED = {":", "[x]", "[c]", "[z]", "..", "-", "", "x", "c"}


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip().lower() if v is not None else ""


def _matches(cell: str, patterns: list[str]) -> bool:
    return any(re.search(p, cell) for p in patterns)


def _month_end(year: int, month: int) -> date:
    return (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).date()


def parse_period(header) -> date | None:
    """'Year ending Mar 2024' / 'Mar-2024' / datetime cell -> month-end date."""
    if isinstance(header, (datetime, pd.Timestamp)):
        return _month_end(header.year, header.month)
    m = PERIOD_RE.search(str(header))
    if not m:
        return None
    return _month_end(int(m.group(2)), MONTHS[m.group(1)[:3].lower()])


def find_header_row(raw: pd.DataFrame, max_scan: int = 40) -> int | None:
    for i in range(min(max_scan, len(raw))):
        cells = [_norm(v) for v in raw.iloc[i].tolist()]
        if any(_matches(c, CODE_PATTERNS) for c in cells) and \
           any(_matches(c, NAME_PATTERNS) for c in cells):
            return i
    return None


def _to_number(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    if s in SUPPRESSED:
        return None
    s = s.replace(",", "").replace("£", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn one raw sheet (no header applied) into the long format."""
    h = find_header_row(raw)
    if h is None:
        raise ValueError("No header row with an area code and name column")
    headers = raw.iloc[h].tolist()
    norm = [_norm(v) for v in headers]
    code_col = next(i for i, c in enumerate(norm) if _matches(c, CODE_PATTERNS))
    name_col = next(i for i, c in enumerate(norm) if _matches(c, NAME_PATTERNS))
    period_cols = {i: p for i, v in enumerate(headers) if (p := parse_period(v))}
    if not period_cols:
        raise ValueError("Header row found but no period columns")

    records = []
    for _, row in raw.iloc[h + 1:].iterrows():
        code = row.iloc[code_col]
        if code is None or pd.isna(code) or not str(code).strip():
            continue  # blank spacer or end-of-table notes
        code = str(code).strip()
        if not re.match(r"^[A-Z]\d{8}$", code):
            continue  # footnotes such as "Source: ONS" land in the code column
        name = str(row.iloc[name_col]).strip()
        for col, period in period_cols.items():
            records.append((code, name, period, _to_number(row.iloc[col])))
    out = pd.DataFrame(records, columns=["area_code", "area_name", "period_end", "value"])
    if out.empty:
        raise ValueError("Header found but no data rows with ONS area codes")
    return out


def parse_workbook(path: Path, sheet_hint: str | None = None) -> pd.DataFrame:
    """Parse the first sheet that matches `sheet_hint` (case-insensitive substring)
    and has a recognisable table; without a hint, the first sheet with a table."""
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    names = list(sheets)
    if sheet_hint:
        names = [n for n in names if sheet_hint.lower() in n.lower()] or names
    errors = {}
    for name in names:
        try:
            df = parse_sheet(sheets[name])
            log(LOG, "parsed sheet", file=path.name, sheet=name, rows=len(df),
                areas=df["area_code"].nunique(), periods=df["period_end"].nunique())
            return df.assign(sheet=name)
        except ValueError as exc:
            errors[name] = str(exc)
    raise ValueError(f"No parsable sheet in {path.name}: {errors}")


def reconcile_with_warehouse(ons: pd.DataFrame, warehouse_path: Path) -> pd.DataFrame:
    """Compare ONS December year-end medians with this pipeline's district medians.

    Differences are expected (ONS uses its own cut of the same Land Registry
    data), but a large gap points to a bug on one side.
    """
    import duckdb

    dec = ons[pd.to_datetime(ons["period_end"]).dt.month == 12].copy()
    dec["year"] = pd.to_datetime(dec["period_end"]).dt.year
    dec["district"] = dec["area_name"].str.upper()
    con = duckdb.connect(str(warehouse_path), read_only=True)
    ours = con.execute(
        "select district, year, median_price_gbp from reporting.rpt_district_annual").df()
    merged = dec.merge(ours, on=["district", "year"], how="inner")
    merged["pct_diff"] = merged["median_price_gbp"] / merged["value"] - 1
    return merged[["area_code", "district", "year", "value", "median_price_gbp", "pct_diff"]]
