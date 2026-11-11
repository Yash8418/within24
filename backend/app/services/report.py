"""A printable PDF record of hours worked, for the student's own records or to show an advisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fpdf import FPDF

from app.models import JobType, SchoolBreak, Shift, User
from app.rules.engine import (
    LIMITED_JOB_TYPES,
    Break,
    limited_segments,
    minutes_between,
    peak_rolling_window,
    weekly_totals,
)
from app.rules.ruleset import RuleSet
from app.schemas import as_utc
from app.services.hours import local_midnight, to_period

TYPE_LABELS = {JobType.OFF_CAMPUS: "Off-campus", JobType.ON_CAMPUS: "On-campus", JobType.GIG: "Gig / app-based"}
STATUS_LABELS = {"ok": "Within limit", "warning": "Close to limit", "over": "Over limit"}
NAVY = (22, 58, 95)
RED = (179, 38, 30)
GREY = (90, 98, 110)


def _text(value: str) -> str:
    """The built-in PDF fonts only cover Latin-1; swap common typographic characters and drop the rest."""
    for a, b in {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "..."}.items():
        value = value.replace(a, b)
    return value.encode("latin-1", "replace").decode("latin-1")


def _hours(minutes: float) -> str:
    return f"{minutes / 60:.2f}"


@dataclass(frozen=True)
class WeekRow:
    start: date
    counted: float  # off-campus + gig minutes that count toward the limit
    on_campus: float
    in_break: float  # off-campus + gig minutes worked during a scheduled break
    limit: int
    status: str


@dataclass(frozen=True)
class ShiftRow:
    shift: Shift
    worked: int  # minutes worked (earning minutes for gig)
    counted: float | None  # None for on-campus work, which has no limit


def summarize(
    shifts: list[Shift], breaks: list[Break], tz: ZoneInfo, ruleset: RuleSet, first_day: date, last_day: date
) -> tuple[list[WeekRow], list[ShiftRow]]:
    periods = [to_period(s) for s in shifts]
    segments = limited_segments(periods, breaks, tz)
    totals = weekly_totals(segments, tz, ruleset, first_day, last_day)

    weeks = []
    for total in totals:
        lo, hi = local_midnight(total.week_start, tz), local_midnight(total.week_start + timedelta(days=7), tz)
        on_campus = in_break_worked = 0.0
        for period in periods:
            share = max((min(period.end, hi) - max(period.start, lo)) / (period.end - period.start), 0)
            if period.job_type in LIMITED_JOB_TYPES:
                in_break_worked += period.counted_minutes * share
            else:
                on_campus += period.counted_minutes * share
        weeks.append(
            WeekRow(total.week_start, total.minutes, on_campus, in_break_worked - total.minutes, total.limit_minutes, total.status)
        )

    rows = []
    for shift, period in zip(shifts, periods, strict=True):
        if period.job_type in LIMITED_JOB_TYPES:
            counted = minutes_between(limited_segments([period], breaks, tz), period.start, period.end)
        else:
            counted = None
        rows.append(ShiftRow(shift, period.counted_minutes, counted))
    return weeks, rows


class HoursPDF(FPDF):
    def __init__(self, footer_note: str):
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.footer_note = footer_note
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", size=7.5)
        self.set_text_color(*GREY)
        self.cell(0, 4, _text(self.footer_note), align="L")
        self.cell(0, 4, f"Page {self.page_no()} of {{nb}}", align="R", new_x="LMARGIN", new_y="NEXT")

    def heading(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*NAVY)
        self.cell(0, 8, _text(text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)

    def table(self, headers: list[str], widths: list[float], rows: list[list[str]], aligns: str, red_rows=()):
        def header_row():
            self.set_font("Helvetica", "B", 8.5)
            self.set_fill_color(234, 239, 245)
            for text, width, align in zip(headers, widths, aligns, strict=True):
                self.cell(width, 7, _text(text), border="B", align=align, fill=True)
            self.ln()

        header_row()
        self.set_font("Helvetica", size=8.5)
        for index, row in enumerate(rows):
            if self.will_page_break(6.5):
                self.add_page()
                header_row()
                self.set_font("Helvetica", size=8.5)
            self.set_text_color(*(RED if index in red_rows else (0, 0, 0)))
            for text, width, align in zip(row, widths, aligns, strict=True):
                self.cell(width, 6.5, _text(text), border="B", align=align)
            self.ln()
        self.set_text_color(0, 0, 0)


def build_hours_pdf(
    user: User,
    shifts: list[Shift],
    school_breaks: list[SchoolBreak],
    ruleset: RuleSet,
    first_day: date,
    last_day: date,
    now: datetime | None = None,
) -> bytes:
    tz = ZoneInfo(user.timezone)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    breaks = [Break(b.start_date, b.end_date) for b in school_breaks]
    weeks, rows = summarize(shifts, breaks, tz, ruleset, first_day, last_day)
    period_lo, period_hi = local_midnight(first_day, tz), local_midnight(last_day + timedelta(days=1), tz)
    rows = [r for r in rows if as_utc(r.shift.ends_at) > period_lo and as_utc(r.shift.starts_at) < period_hi]

    pdf = HoursPDF(f"Within24 - self-recorded hours, generated {now:%b %d, %Y %H:%M} ({user.timezone}). Not an official IRCC document.")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 9, "Work hours record", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=10)
    name = user.full_name or user.email
    pdf.cell(0, 5.5, _text(f"{name}  ({user.email})" if user.full_name else name), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0, 5.5, _text(f"Weeks of {weeks[0].start:%b %d, %Y} to {last_day:%b %d, %Y}  -  times in {user.timezone}"),
        new_x="LMARGIN", new_y="NEXT",
    )

    total_counted = sum(w.counted for w in weeks)
    over = [w for w in weeks if w.status == "over"]
    peak = peak_rolling_window(limited_segments([to_period(s) for s in shifts], breaks, tz), ruleset)
    pdf.ln(3)
    pdf.set_font("Helvetica", size=9.5)
    facts = [
        ("Off-campus limit", f"{ruleset.off_campus_weekly_limit_hours:g} hours per week during academic sessions (rules as of {ruleset.effective_from:%b %d, %Y})"),
        ("Counted hours", f"{_hours(total_counted)} h over {len(weeks)} weeks (average {_hours(total_counted / len(weeks))} h/week)"),
        ("Weeks over the limit", str(len(over)) if over else "None"),
    ]
    if peak:
        facts.append(
            ("Busiest 7 days", f"{_hours(peak.minutes)} h, {peak.window_start.astimezone(tz):%b %d %H:%M} to {peak.window_end.astimezone(tz):%b %d %H:%M}")
        )
    for label, value in facts:
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(42, 5.5, _text(label))
        pdf.set_font("Helvetica", size=9.5)
        pdf.cell(0, 5.5, _text(value), new_x="LMARGIN", new_y="NEXT")

    pdf.heading("Weekly totals")
    pdf.table(
        ["Week (Mon-Sun)", "Counted (h)", "During break (h)", "On-campus (h)", "", "Status"],
        [52, 26, 32, 28, 6, 40],
        [
            [
                f"{w.start:%b %d} - {w.start + timedelta(days=6):%b %d, %Y}",
                _hours(w.counted),
                _hours(w.in_break) if w.in_break >= 0.5 else "-",
                _hours(w.on_campus) if w.on_campus >= 0.5 else "-",
                "",
                STATUS_LABELS[w.status],
            ]
            for w in weeks
        ],
        "LRRRLL",
        red_rows={i for i, w in enumerate(weeks) if w.status == "over"},
    )

    if school_breaks:
        pdf.heading("Scheduled breaks (hours not counted)")
        pdf.set_font("Helvetica", size=9)
        for b in school_breaks:
            pdf.cell(0, 5.5, _text(f"{b.name}: {b.start_date:%b %d, %Y} - {b.end_date:%b %d, %Y}"), new_x="LMARGIN", new_y="NEXT")

    pdf.heading(f"Shifts ({len(rows)})")
    if not rows:
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 6, "No shifts recorded in this period.", new_x="LMARGIN", new_y="NEXT")
    else:
        table_rows = []
        for r in rows:
            # Stored datetimes can come back without tzinfo (SQLite); they are UTC.
            start, end = as_utc(r.shift.starts_at).astimezone(tz), as_utc(r.shift.ends_at).astimezone(tz)
            ends = f"{end:%H:%M}" if end.date() == start.date() else f"{end:%H:%M} (+1)"
            counted = "no limit" if r.counted is None else _hours(r.counted)
            table_rows.append(
                [
                    f"{start:%a %b %d}",
                    f"{start:%H:%M} - {ends}",
                    (r.shift.job.name or "")[:28],
                    TYPE_LABELS[r.shift.job.job_type],
                    _hours(r.worked),
                    counted,
                ]
            )
        pdf.table(
            ["Date", "Time", "Job", "Type", "Worked (h)", "Counted (h)"],
            [26, 34, 50, 28, 22, 24],
            table_rows,
            "LLLLRR",
        )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(
        0, 4,
        _text(
            "For gig work, 'worked' is the time spent earning wages or commission. Hours at on-campus jobs have no limit. "
            "Off-campus hours during scheduled school breaks don't count toward the limit. This record is prepared by the "
            "student from their own entries; check current rules at canada.ca before relying on it."
        ),
    )
    return bytes(pdf.output())
