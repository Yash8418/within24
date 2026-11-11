"""Parse a CSV of shifts (e.g. an export from a delivery or rideshare app) into shift data.

Accepted columns (header names are case-insensitive; extra columns are ignored):

    date            2026-11-03, or Nov 3 2026 / 3 Nov 2026   (required unless start/end include a date)
    start, end      18:00, 6:00 PM, 6pm, or a full "2026-11-03 18:00"
    earning_minutes minutes actually spent earning (gig work). Aliases: active_minutes, engaged_minutes
    earning_hours   same, in hours (e.g. 2.5).                    Aliases: active_hours, engaged_hours
    notes           free text.                                     Aliases: note, description

Times are local to the user's timezone. A shift whose end is not after its start is taken to end the
next day (an overnight shift). Dates must be unambiguous, so 03/11/2026-style dates are rejected.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MAX_ROWS = 2000

ALIASES = {
    "date": ("date", "day", "shift_date"),
    "start": ("start", "start_time", "starts_at", "clock_in", "begin"),
    "end": ("end", "end_time", "ends_at", "clock_out", "finish"),
    "earning_minutes": ("earning_minutes", "active_minutes", "engaged_minutes"),
    "earning_hours": ("earning_hours", "active_hours", "engaged_hours"),
    "notes": ("notes", "note", "description"),
}

DATE_FORMATS = ("%Y-%m-%d", "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y")
TIME_FORMATS = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p", "%I %p")


class RowError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedShift:
    line: int
    starts_at: datetime  # UTC
    ends_at: datetime
    earning_minutes: int | None
    notes: str | None


@dataclass
class ParseResult:
    shifts: list[ParsedShift]
    errors: list[tuple[int, str]]  # (line number, message)


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


def _columns(headers: list[str]) -> dict[str, str]:
    """Map each known field to the header that holds it."""
    keyed = {_key(h): h for h in headers if h}
    found = {}
    for field, names in ALIASES.items():
        for name in names:
            if name in keyed:
                found[field] = keyed[name]
                break
    return found


def parse_date(value: str) -> date:
    """
    >>> parse_date("2026-11-03"), parse_date("Nov 3, 2026"), parse_date("3 November 2026")
    (datetime.date(2026, 11, 3), datetime.date(2026, 11, 3), datetime.date(2026, 11, 3))
    """
    cleaned = re.sub(r"\s+", " ", value.replace(",", " ")).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", cleaned):
        raise RowError(f"date '{value}' is ambiguous - use YYYY-MM-DD (e.g. 2026-11-03)")
    raise RowError(f"can't read the date '{value}' - use YYYY-MM-DD")


def parse_time(value: str) -> time:
    """
    >>> parse_time("18:05"), parse_time("6:05 pm"), parse_time("6pm"), parse_time("12 AM")
    (datetime.time(18, 5), datetime.time(18, 5), datetime.time(18, 0), datetime.time(0, 0))
    """
    cleaned = re.sub(r"\s*([ap])\.?m\.?$", r" \1M", value.strip(), flags=re.IGNORECASE).upper()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    raise RowError(f"can't read the time '{value}' - use 24-hour HH:MM (e.g. 18:30) or 6:30 PM")


def _split_datetime(value: str) -> tuple[str | None, str]:
    """'2026-11-03 18:00' -> ('2026-11-03', '18:00'); '18:00' -> (None, '18:00')."""
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](.+)", value.strip())
    return (match.group(1), match.group(2)) if match else (None, value)


def _minutes(row: dict, columns: dict[str, str], length: int) -> int | None:
    if "earning_minutes" in columns and row.get(columns["earning_minutes"], "").strip():
        raw, factor, label = row[columns["earning_minutes"]], 1, "earning minutes"
    elif "earning_hours" in columns and row.get(columns["earning_hours"], "").strip():
        raw, factor, label = row[columns["earning_hours"]], 60, "earning hours"
    else:
        return None
    try:
        minutes = round(float(raw.strip()) * factor)
    except ValueError:
        raise RowError(f"{label} '{raw}' is not a number") from None
    if minutes < 0:
        raise RowError(f"{label} can't be negative")
    if minutes > length:
        raise RowError(f"{label} ({minutes} min) is longer than the shift ({length} min)")
    return minutes


def _parse_row(row: dict, columns: dict[str, str], tz: ZoneInfo, line: int) -> ParsedShift:
    start_date, start_text = _split_datetime(row.get(columns["start"], "") or "")
    end_date, end_text = _split_datetime(row.get(columns["end"], "") or "")
    if not start_text.strip() or not end_text.strip():
        raise RowError("start and end times are required")

    day_text = (row.get(columns["date"], "") if "date" in columns else "").strip() or start_date
    if not day_text:
        raise RowError("a date is required")
    day = parse_date(day_text)
    starts = datetime.combine(day, parse_time(start_text), tz)
    ends = datetime.combine(parse_date(end_date) if end_date else day, parse_time(end_text), tz)
    if ends <= starts and not end_date:
        ends = datetime.combine(ends.date() + timedelta(days=1), ends.timetz())  # overnight shift
    # Do the arithmetic in UTC: subtracting two datetimes in the same zone ignores DST changes.
    starts, ends = starts.astimezone(UTC), ends.astimezone(UTC)
    if ends <= starts:
        raise RowError("the shift ends before it starts")
    if ends - starts > timedelta(hours=24):
        raise RowError("a single shift can't be longer than 24 hours")

    length = int((ends - starts).total_seconds() // 60)
    notes = (row.get(columns["notes"], "") if "notes" in columns else "").strip() or None
    return ParsedShift(line, starts, ends, _minutes(row, columns, length), notes[:1000] if notes else None)


def parse_shifts_csv(text: str, tz_name: str) -> ParseResult:
    tz = ZoneInfo(tz_name)
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    columns = _columns(reader.fieldnames or [])
    missing = [name for name in ("start", "end") if name not in columns]
    if missing:
        found = ", ".join(reader.fieldnames or []) or "none"
        return ParseResult([], [(1, f"missing column(s): {', '.join(missing)} (found: {found})")])

    result = ParseResult([], [])
    for index, row in enumerate(reader):
        line = index + 2  # header is line 1
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue  # blank line
        if len(result.shifts) + len(result.errors) >= MAX_ROWS:
            result.errors.append((line, f"too many rows - import at most {MAX_ROWS} at a time"))
            break
        try:
            result.shifts.append(_parse_row(row, columns, tz, line))
        except RowError as error:
            result.errors.append((line, str(error)))
    return result
