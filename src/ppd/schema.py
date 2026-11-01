"""Published layout of HM Land Registry Price Paid Data and raw-file validation.

Source: https://www.gov.uk/about-the-price-paid-data
Files have no header row. Yearly/complete files and the monthly change file
share the same 16 columns; record_status is always "A" outside the monthly file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

RAW_COLUMNS: list[str] = [
    "transaction_id",
    "price",
    "date_of_transfer",
    "postcode",
    "property_type",
    "old_new",
    "duration",
    "paon",
    "saon",
    "street",
    "locality",
    "town_city",
    "district",
    "county",
    "ppd_category",
    "record_status",
]

PROPERTY_TYPES = {
    "D": "Detached",
    "S": "Semi-detached",
    "T": "Terraced",
    "F": "Flat/maisonette",
    "O": "Other",
}
OLD_NEW = {"Y": "New build", "N": "Established"}
DURATIONS = {"F": "Freehold", "L": "Leasehold", "U": "Unknown"}
PPD_CATEGORIES = {"A": "Standard", "B": "Additional"}
RECORD_STATUSES = {"A": "Addition", "C": "Change", "D": "Delete"}

# {GUID} in upper-case hex, as published
GUID_PATTERN = r"^\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}$"
# Full UK postcode with a single space; blank postcodes are allowed (they occur)
POSTCODE_PATTERN = r"^[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2}$"

RAW_SCHEMA = pa.DataFrameSchema(
    {
        "transaction_id": pa.Column(str, pa.Check.str_matches(GUID_PATTERN), nullable=False),
        "price": pa.Column(int, pa.Check.gt(0), nullable=False),
        "date_of_transfer": pa.Column(
            "datetime64[ns]", pa.Check.ge(pd.Timestamp("1995-01-01")), nullable=False
        ),
        "postcode": pa.Column(str, pa.Check.str_matches(POSTCODE_PATTERN), nullable=True),
        "property_type": pa.Column(str, pa.Check.isin(list(PROPERTY_TYPES))),
        "old_new": pa.Column(str, pa.Check.isin(list(OLD_NEW))),
        "duration": pa.Column(str, pa.Check.isin(list(DURATIONS))),
        "paon": pa.Column(str, nullable=True),
        "saon": pa.Column(str, nullable=True),
        "street": pa.Column(str, nullable=True),
        "locality": pa.Column(str, nullable=True),
        "town_city": pa.Column(str, nullable=True),
        "district": pa.Column(str, nullable=False),
        "county": pa.Column(str, nullable=False),
        "ppd_category": pa.Column(str, pa.Check.isin(list(PPD_CATEGORIES))),
        "record_status": pa.Column(str, pa.Check.isin(list(RECORD_STATUSES))),
    },
    strict=True,
    coerce=False,
)


def read_raw_chunks(path: Path, chunksize: int = 250_000):
    """Yield typed DataFrame chunks from a headerless Price Paid CSV."""
    reader = pd.read_csv(
        path,
        header=None,
        names=RAW_COLUMNS,
        dtype=str,
        keep_default_na=False,
        chunksize=chunksize,
    )
    for chunk in reader:
        chunk = chunk.replace({"": None})
        chunk["price"] = pd.to_numeric(chunk["price"], errors="coerce").astype("Int64")
        chunk["date_of_transfer"] = pd.to_datetime(
            chunk["date_of_transfer"], format="%Y-%m-%d %H:%M", errors="coerce"
        )
        yield chunk


def validate_file(path: Path, max_error_rate: float = 0.001) -> dict:
    """Validate a whole raw file chunk by chunk.

    Returns a report. Raises ValueError when the share of failing rows is above
    `max_error_rate` (a few malformed postcodes are normal in this dataset;
    a wrong column layout is not).
    """
    rows = 0
    failing_rows: set[int] = set()
    failures_by_check: dict[str, int] = {}
    offset = 0
    for chunk in read_raw_chunks(path):
        rows += len(chunk)
        chunk = chunk.reset_index(drop=True)
        chunk["price"] = chunk["price"].astype("float").fillna(-1).astype(int)
        try:
            RAW_SCHEMA.validate(chunk, lazy=True)
        except SchemaErrors as err:
            fc = err.failure_cases
            for (col, check), n in fc.groupby(["column", "check"]).size().items():
                key = f"{col}:{check}"
                failures_by_check[key] = failures_by_check.get(key, 0) + int(n)
            idx = fc["index"].dropna().astype(int) + offset
            failing_rows.update(idx.tolist())
        offset += len(chunk)

    error_rate = (len(failing_rows) / rows) if rows else 1.0
    report = {
        "file": path.name,
        "rows": rows,
        "failing_rows": len(failing_rows),
        "error_rate": round(error_rate, 6),
        "failures_by_check": dict(sorted(failures_by_check.items())),
        "passed": rows > 0 and error_rate <= max_error_rate,
    }
    if not report["passed"]:
        raise ValueError(f"Raw validation failed for {path.name}: {report}")
    return report
