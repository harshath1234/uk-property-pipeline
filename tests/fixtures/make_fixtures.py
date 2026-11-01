"""Generate small SYNTHETIC files in the exact Price Paid Data layout.

These are test fixtures only. They are random, contain no real addresses, and
must never be used for any figure in the README, dashboard or CV. Real figures
come only from `make run` on the downloaded HM Land Registry files.

Usage: python tests/fixtures/make_fixtures.py tests/fixtures/ppd
"""

from __future__ import annotations

import csv
import random
import sys
import uuid
from pathlib import Path

PLACES = [
    ("MANCHESTER", "MANCHESTER", "GREATER MANCHESTER", "M"),
    ("SALFORD", "SALFORD", "GREATER MANCHESTER", "M"),
    ("NOTTINGHAM", "CITY OF NOTTINGHAM", "CITY OF NOTTINGHAM", "NG"),
    ("LEEDS", "LEEDS", "WEST YORKSHIRE", "LS"),
    ("BRISTOL", "CITY OF BRISTOL", "CITY OF BRISTOL", "BS"),
    ("LONDON", "CAMDEN", "GREATER LONDON", "NW"),
    ("CARDIFF", "CARDIFF", "CARDIFF", "CF"),
]
TYPES = ["D", "S", "T", "F", "O"]
TYPE_PRICE = {"D": 420_000, "S": 280_000, "T": 230_000, "F": 210_000, "O": 350_000}


def _guid(rng: random.Random) -> str:
    return "{" + str(uuid.UUID(int=rng.getrandbits(128))).upper() + "}"


def _row(rng: random.Random, year: int, status: str = "A", tid: str | None = None) -> list[str]:
    town, district, county, area = rng.choice(PLACES)
    ptype = rng.choices(TYPES, weights=[20, 28, 27, 22, 3])[0]
    price = int(TYPE_PRICE[ptype] * rng.lognormvariate(0, 0.35)) // 100 * 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    postcode = "" if rng.random() < 0.01 else (
        f"{area}{rng.randint(1, 20)} {rng.randint(1, 9)}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}"
        f"{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}"
    )
    return [
        tid or _guid(rng),
        str(max(price, 10_000)),
        f"{year}-{month:02d}-{day:02d} 00:00",
        postcode,
        ptype,
        "Y" if rng.random() < 0.08 else "N",
        "L" if ptype == "F" else rng.choice(["F", "F", "F", "L"]),
        str(rng.randint(1, 250)),
        "" if ptype != "F" else f"FLAT {rng.randint(1, 40)}",
        "SYNTHETIC STREET",
        "",
        town,
        district,
        county,
        "A" if rng.random() < 0.88 else "B",
        status,
    ]


def write(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    yearly: dict[int, list[list[str]]] = {}
    for year in (2023, 2024, 2025):
        yearly[year] = [_row(rng, year) for _ in range(400)]
        write(out / f"pp-{year}.csv", yearly[year])

    # Monthly change file: 60 additions, 15 changes (price corrected), 10 deletes
    monthly = [_row(rng, 2025) for _ in range(60)]
    for r in rng.sample(yearly[2025], 15):
        changed = list(r)
        changed[1] = str(int(r[1]) + 5_000)
        changed[15] = "C"
        monthly.append(changed)
    for r in rng.sample(yearly[2024], 10):
        deleted = list(r)
        deleted[15] = "D"
        monthly.append(deleted)
    write(out / "pp-monthly-update-new-version.csv", monthly)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/ppd")
