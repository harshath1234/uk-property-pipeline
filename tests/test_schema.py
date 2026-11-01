from __future__ import annotations

import pytest

from ppd.schema import validate_file


def test_fixture_files_pass(fixture_dir):
    for f in fixture_dir.glob("pp-*.csv"):
        report = validate_file(f)
        assert report["passed"], report


def test_bad_codes_fail(tmp_path, fixture_dir):
    lines = (fixture_dir / "pp-2024.csv").read_text().splitlines()
    # corrupt 5% of rows: property type "X" is not a published code
    bad = [ln.replace('"S","N"', '"X","N"', 1) if i % 20 == 0 else ln
           for i, ln in enumerate(lines)]
    path = tmp_path / "pp-bad.csv"
    path.write_text("\n".join(bad) + "\n")
    with pytest.raises(ValueError, match="property_type"):
        validate_file(path)


def test_wrong_column_count_fails(tmp_path):
    path = tmp_path / "pp-short.csv"
    path.write_text('"{00000000-0000-0000-0000-000000000000}","100000","2024-01-01 00:00"\n')
    with pytest.raises(ValueError):
        validate_file(path)
