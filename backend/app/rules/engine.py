"""Work-hours engine: totals off-campus hours against the weekly limit.

Core idea: every shift becomes a `Segment` — a time span plus the number of minutes
that count toward the limit. Segments can be cut at any instant (a week boundary,
the start of a break), and counted minutes are split in proportion to time. That
also handles gig shifts, where only part of the logged time was spent earning.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models import JobType
from app.rules.ruleset import RuleSet

WEEK = timedelta(days=7)
LIMITED_JOB_TYPES = {JobType.OFF_CAMPUS, JobType.GIG}


@dataclass(frozen=True)
class Segment:
    start: datetime
    end: datetime
    minutes: float  # minutes that count toward the limit, spread evenly over [start, end)

    def clip(self, lo: datetime, hi: datetime) -> Segment | None:
        """The part of this segment inside [lo, hi), with minutes scaled proportionally."""
        start, end = max(self.start, lo), min(self.end, hi)
        if start >= end:
            return None
        share = (end - start) / (self.end - self.start)
        return Segment(start, end, self.minutes * share)


@dataclass(frozen=True)
class WorkPeriod:
    """One shift as the engine sees it."""

    start: datetime
    end: datetime
    counted_minutes: int
    job_type: JobType


@dataclass(frozen=True)
class Break:
    """A scheduled academic break, inclusive of both dates, in the user's timezone."""

    start_date: date
    end_date: date


@dataclass(frozen=True)
class WeekTotal:
    week_start: date
    minutes: float
    limit_minutes: int
    status: str  # "ok" | "warning" | "over"


@dataclass(frozen=True)
class RollingPeak:
    window_start: datetime
    window_end: datetime
    minutes: float
    status: str


def _status(minutes: float, ruleset: RuleSet) -> str:
    limit = ruleset.weekly_limit_minutes
    if minutes > limit + 1e-6:
        return "over"
    if minutes >= limit * ruleset.warning_threshold:
        return "warning"
    return "ok"


def _local_midnight(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


def limited_segments(periods: Iterable[WorkPeriod], breaks: Iterable[Break], tz: ZoneInfo) -> list[Segment]:
    """Segments that count toward the off-campus limit: off-campus and gig work, minus scheduled breaks."""
    break_spans = sorted(
        (_local_midnight(b.start_date, tz), _local_midnight(b.end_date + timedelta(days=1), tz)) for b in breaks
    )
    segments: list[Segment] = []
    for period in periods:
        if period.job_type not in LIMITED_JOB_TYPES or period.counted_minutes <= 0:
            continue
        pieces = [Segment(period.start, period.end, float(period.counted_minutes))]
        for break_start, break_end in break_spans:
            next_pieces = []
            for piece in pieces:
                for lo, hi in ((piece.start, break_start), (break_end, piece.end)):
                    part = piece.clip(lo, hi)
                    if part:
                        next_pieces.append(part)
            pieces = next_pieces
        segments.extend(pieces)
    return sorted(segments, key=lambda s: s.start)


def minutes_between(segments: Iterable[Segment], lo: datetime, hi: datetime) -> float:
    return sum(part.minutes for s in segments if (part := s.clip(lo, hi)))


def week_start_for(day: date, week_starts_on: int) -> date:
    """First day of the week containing `day`. week_starts_on: 0 = Monday ... 6 = Sunday."""
    return day - timedelta(days=(day.weekday() - week_starts_on) % 7)


def weekly_totals(
    segments: list[Segment],
    tz: ZoneInfo,
    ruleset: RuleSet,
    first_day: date,
    last_day: date,
    week_starts_on: int = 0,
) -> list[WeekTotal]:
    """Calendar-week totals for every week touching [first_day, last_day]."""
    totals = []
    week = week_start_for(first_day, week_starts_on)
    while week <= last_day:
        minutes = minutes_between(segments, _local_midnight(week, tz), _local_midnight(week + timedelta(days=7), tz))
        totals.append(WeekTotal(week, round(minutes, 1), ruleset.weekly_limit_minutes, _status(minutes, ruleset)))
        week += timedelta(days=7)
    return totals


def peak_rolling_window(segments: list[Segment], ruleset: RuleSet) -> RollingPeak | None:
    """The 7-day window (any start time) with the most counted minutes.

    The minutes inside a sliding window change piecewise-linearly as the window moves,
    so the maximum is always reached when one of the window's edges lines up with
    the start or end of a segment. Checking those candidate positions is exact.
    """
    if not segments:
        return None
    candidates = set()
    for s in segments:
        candidates.update({s.start, s.end, s.start - WEEK, s.end - WEEK})

    best_start, best_minutes = None, -1.0
    for start in sorted(candidates):
        minutes = minutes_between(segments, start, start + WEEK)
        if minutes > best_minutes + 1e-9:
            best_start, best_minutes = start, minutes
    return RollingPeak(best_start, best_start + WEEK, round(best_minutes, 1), _status(best_minutes, ruleset))
