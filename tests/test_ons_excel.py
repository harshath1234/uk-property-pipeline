"""The ONS parser against two workbook layouts that differ the way real
releases do (title/notes rows, header wording, sheet names, period format,
suppression markers). Values are invented for the test."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from openpyxl import Workbook

from ppd.ons_excel import parse_period, parse_workbook


def _older_layout(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["HPSSA Dataset 9. Median price paid by local authority"])
    ws.append(["Notes: values below are for testing only"])
    ws.append([])
    ws.append(["Local authority code", "Local authority name",
               "Year ending Dec 2023", "Year ending Mar 2024"])
    ws.append(["E08000003", "Manchester", 230000, "235,500"])
    ws.append(["E06000018", "Nottingham", ":", 190000])
    ws.append([])
    ws.append(["Source: Office for National Statistics"])
    wb.save(path)


def _newer_layout(path):
    wb = Workbook()
    wb.active.title = "Contents"
    wb.active.append(["This workbook contains the following tables"])
    notes = wb.create_sheet("Notes")
    notes.append(["Note 1", "[x] = not available"])
    t = wb.create_sheet("2a")
    t.append(["Table 2a: Median price paid"])
    t.append(["Some cells are suppressed [x]"])
    t.append(["Region code", "Region name", "LA code", "LA name",
              datetime(2023, 12, 1), datetime(2024, 3, 1)])
    t.append(["E12000002", "North West", "E08000003", "Manchester", 231000, 236000])
    t.append(["E12000004", "East Midlands", "E06000018", "Nottingham", "[x]", 191000])
    wb.save(path)


@pytest.mark.parametrize("builder,hint", [(_older_layout, None), (_newer_layout, "2a")])
def test_both_layouts_give_the_same_shape(tmp_path, builder, hint):
    path = tmp_path / "hpssa.xlsx"
    builder(path)
    df = parse_workbook(path, sheet_hint=hint)
    assert list(df.columns[:4]) == ["area_code", "area_name", "period_end", "value"]
    assert set(df["area_code"]) == {"E08000003", "E06000018"}
    assert set(df["period_end"]) == {date(2023, 12, 31), date(2024, 3, 31)}
    nott_dec = df[(df.area_code == "E06000018") & (df.period_end == date(2023, 12, 31))]
    assert nott_dec["value"].isna().all()          # suppression marker -> NULL
    assert len(df) == 4                             # footer/notes rows ignored


def test_without_hint_skips_sheets_with_no_table(tmp_path):
    path = tmp_path / "hpssa.xlsx"
    _newer_layout(path)
    assert parse_workbook(path)["sheet"].iloc[0] == "2a"


def test_thousands_separator_parsed(tmp_path):
    path = tmp_path / "hpssa.xlsx"
    _older_layout(path)
    df = parse_workbook(path)
    v = df[(df.area_code == "E08000003") & (df.period_end == date(2024, 3, 31))]["value"]
    assert v.iloc[0] == 235500


@pytest.mark.parametrize("text,expected", [
    ("Year ending Mar 2024", date(2024, 3, 31)),
    ("Sep-2019", date(2019, 9, 30)),
    ("year ending december 2020", date(2020, 12, 31)),
    ("Local authority name", None),
])
def test_parse_period(text, expected):
    assert parse_period(text) == expected


def test_unrecognisable_workbook_fails_clearly(tmp_path):
    wb = Workbook()
    wb.active.append(["nothing", "useful"])
    path = tmp_path / "bad.xlsx"
    wb.save(path)
    with pytest.raises(ValueError, match="No parsable sheet"):
        parse_workbook(path)
