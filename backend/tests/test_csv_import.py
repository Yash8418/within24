from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.csv_import import parse_shifts_csv

TZ = ZoneInfo("America/Toronto")


def test_reads_a_gig_export_with_active_hours():
    text = (
        "﻿Date,Start Time,End Time,Active Hours,Description\n"
        "2026-11-03,6:00 PM,9:30 PM,2.25,Dinner rush\n"
        "Nov 4 2026,22:00,01:30,,Late shift\n"
        "\n"
    )
    result = parse_shifts_csv(text, "America/Toronto")
    assert result.errors == []
    first, overnight = result.shifts
    assert first.starts_at == datetime(2026, 11, 3, 18, 0, tzinfo=TZ)  # compares the instant
    assert first.earning_minutes == 135 and first.notes == "Dinner rush"
    assert overnight.ends_at == datetime(2026, 11, 5, 1, 30, tzinfo=TZ)  # rolls over to the next day
    assert overnight.earning_minutes is None


def test_accepts_full_datetimes_without_a_date_column():
    text = "clock_in,clock_out,engaged_minutes\n2026-11-03 08:00,2026-11-03 12:00,200\n"
    (shift,) = parse_shifts_csv(text, "America/Toronto").shifts
    assert (shift.ends_at - shift.starts_at).total_seconds() == 4 * 3600
    assert shift.earning_minutes == 200


def test_reports_problems_with_line_numbers():
    text = (
        "date,start,end,earning_minutes\n"
        "03/11/2026,09:00,10:00,\n"  # ambiguous date
        "2026-11-03,9am-ish,10:00,\n"  # bad time
        "2026-11-03,09:00,10:00,90\n"  # more earning time than the shift
        "2026-11-03,09:00,10:00,-5\n"
        "2026-11-03,09:00,10:00,45\n"  # fine
    )
    result = parse_shifts_csv(text, "America/Toronto")
    assert [line for line, _ in result.errors] == [2, 3, 4, 5]
    assert "ambiguous" in result.errors[0][1]
    assert "longer than the shift" in result.errors[2][1]
    assert [s.line for s in result.shifts] == [6]


def test_missing_columns_are_reported_once():
    result = parse_shifts_csv("date,hours\n2026-11-03,4\n", "America/Toronto")
    assert result.shifts == []
    assert result.errors[0][0] == 1 and "start, end" in result.errors[0][1]


def test_dst_change_is_handled_in_local_time():
    # Clocks go back at 2 am on Nov 1, 2026 in Toronto: 00:00-04:00 local is 5 real hours.
    (shift,) = parse_shifts_csv("date,start,end\n2026-11-01,00:00,04:00\n", "America/Toronto").shifts
    assert (shift.ends_at - shift.starts_at).total_seconds() == 5 * 3600
