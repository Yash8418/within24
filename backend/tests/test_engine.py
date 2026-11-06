from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models import JobType
from app.rules.engine import (
    Break,
    Segment,
    WorkPeriod,
    limited_segments,
    minutes_between,
    peak_rolling_window,
    week_start_for,
    weekly_totals,
)
from app.rules.ruleset import CURRENT

TZ = ZoneInfo("America/Toronto")


def at(day: int, hour: int, minute: int = 0, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


def shift(day, start_hour, hours, job_type=JobType.OFF_CAMPUS, counted=None, month=11):
    start = at(day, start_hour, month=month)
    end = start + timedelta(hours=hours)
    return WorkPeriod(start, end, counted if counted is not None else int(hours * 60), job_type)


# ---------- Segment ----------
def test_clip_scales_minutes_in_proportion():
    seg = Segment(at(2, 10), at(2, 14), minutes=120)  # e.g. a gig shift: 4 h logged, 2 h earning
    half = seg.clip(at(2, 10), at(2, 12))
    assert half.minutes == pytest.approx(60)
    assert seg.clip(at(2, 15), at(2, 16)) is None


# ---------- Which work counts ----------
def test_on_campus_work_is_not_counted():
    periods = [shift(2, 9, 8), shift(3, 9, 8, JobType.ON_CAMPUS)]
    segments = limited_segments(periods, [], TZ)
    assert sum(s.minutes for s in segments) == 480


def test_gig_counts_only_earning_minutes():
    segments = limited_segments([shift(2, 17, 5, JobType.GIG, counted=150)], [], TZ)
    assert sum(s.minutes for s in segments) == 150


def test_work_during_a_scheduled_break_is_not_counted():
    # Winter break covers Dec 21 - Jan 4 inclusive.
    periods = [shift(22, 9, 10, month=12), shift(18, 9, 6, month=12)]
    segments = limited_segments(periods, [Break(date(2026, 12, 21), date(2027, 1, 4))], TZ)
    assert sum(s.minutes for s in segments) == 360


def test_shift_crossing_into_a_break_is_split_at_midnight():
    # Dec 20 22:00 -> Dec 21 02:00; break starts Dec 21, so only the first 2 hours count.
    period = WorkPeriod(at(20, 22, month=12), at(21, 2, month=12), 240, JobType.OFF_CAMPUS)
    segments = limited_segments([period], [Break(date(2026, 12, 21), date(2026, 12, 31))], TZ)
    assert sum(s.minutes for s in segments) == pytest.approx(120)


# ---------- Calendar weeks ----------
@pytest.mark.parametrize(
    "day, starts_on, expected",
    [(date(2026, 11, 6), 0, date(2026, 11, 2)),   # Friday -> Monday
     (date(2026, 11, 2), 0, date(2026, 11, 2)),   # Monday is its own week start
     (date(2026, 11, 6), 6, date(2026, 11, 1))],  # Sunday-start weeks
)
def test_week_start_for(day, starts_on, expected):
    assert week_start_for(day, starts_on) == expected


def test_weekly_totals_and_statuses():
    # Week of Nov 2: 20 h (ok). Week of Nov 9: 22 h (warning, >= 90% of 24 h). Week of Nov 16: 25 h (over).
    periods = [shift(2, 9, 8), shift(4, 9, 6), shift(6, 9, 6)]
    periods += [shift(9, 9, 8), shift(11, 9, 8), shift(13, 9, 6)]
    periods += [shift(16, 9, 9), shift(18, 9, 8), shift(20, 9, 8)]
    totals = weekly_totals(limited_segments(periods, [], TZ), TZ, CURRENT, date(2026, 11, 2), date(2026, 11, 22))
    assert [(t.week_start.day, t.minutes / 60, t.status) for t in totals] == [
        (2, 20, "ok"), (9, 22, "warning"), (16, 25, "over"),
    ]


def test_exactly_24_hours_is_allowed():
    periods = [shift(2, 9, 8), shift(3, 9, 8), shift(4, 9, 8)]
    totals = weekly_totals(limited_segments(periods, [], TZ), TZ, CURRENT, date(2026, 11, 2), date(2026, 11, 8))
    assert totals[0].minutes == 1440 and totals[0].status == "warning"


def test_overnight_shift_is_split_across_weeks():
    # Sunday Nov 8 20:00 -> Monday Nov 9 04:00: 4 h in each week.
    periods = [WorkPeriod(at(8, 20), at(9, 4), 480, JobType.OFF_CAMPUS)]
    totals = weekly_totals(limited_segments(periods, [], TZ), TZ, CURRENT, date(2026, 11, 2), date(2026, 11, 15))
    assert [t.minutes for t in totals] == [240, 240]


def test_daylight_saving_week_uses_real_elapsed_time():
    # Clocks fall back on Nov 1 2026; a 01:00-03:00 local shift that night is 3 real hours.
    period = WorkPeriod(at(1, 1), at(1, 3), 180, JobType.OFF_CAMPUS)
    totals = weekly_totals(limited_segments([period], [], TZ), TZ, CURRENT, date(2026, 11, 1), date(2026, 11, 1), 6)
    assert totals[0].minutes == 180


# ---------- Rolling 7-day windows ----------
def test_rolling_window_catches_overwork_split_across_calendar_weeks():
    # 16 h at the end of one week + 16 h at the start of the next: each calendar week is fine,
    # but Thursday-to-Wednesday contains 32 h.
    periods = [shift(5, 9, 8), shift(6, 9, 8), shift(9, 9, 8), shift(10, 9, 8)]
    segments = limited_segments(periods, [], TZ)
    weeks = weekly_totals(segments, TZ, CURRENT, date(2026, 11, 2), date(2026, 11, 15))
    assert [w.status for w in weeks] == ["ok", "ok"]

    peak = peak_rolling_window(segments, CURRENT)
    assert peak.minutes == 32 * 60
    assert peak.status == "over"


def test_rolling_peak_is_exact_for_partial_overlaps():
    # Two 10-hour shifts whose combined span (Nov 2 00:00 -> Nov 8 22:00) is under 7 days,
    # so one window holds both entirely.
    periods = [WorkPeriod(at(2, 0), at(2, 10), 600, JobType.OFF_CAMPUS),
               WorkPeriod(at(8, 12), at(8, 22), 600, JobType.OFF_CAMPUS)]
    assert peak_rolling_window(limited_segments(periods, [], TZ), CURRENT).minutes == 1200


def test_rolling_peak_with_shifts_too_far_apart():
    # The second shift starts exactly 7 days + 5 h after the first one starts. Any window that gains
    # an hour of the second shift loses an hour of the first, so the best possible total is 10 h.
    periods = [WorkPeriod(at(2, 0), at(2, 10), 600, JobType.OFF_CAMPUS),
               WorkPeriod(at(9, 5), at(9, 15), 600, JobType.OFF_CAMPUS)]
    peak = peak_rolling_window(limited_segments(periods, [], TZ), CURRENT)
    assert peak.minutes == 600


def test_rolling_peak_matches_brute_force():
    periods = [shift(d, h, n) for d, h, n in [(2, 9, 5), (3, 18, 7), (6, 6, 4), (8, 22, 6), (10, 9, 8), (13, 12, 3)]]
    segments = limited_segments(periods, [], TZ)
    peak = peak_rolling_window(segments, CURRENT)
    brute = max(
        minutes_between(segments, at(1, 0) + timedelta(minutes=15 * i), at(1, 0) + timedelta(minutes=15 * i, days=7))
        for i in range(4 * 24 * 14)
    )
    assert peak.minutes == pytest.approx(brute, abs=0.1)
    assert peak.minutes >= brute - 0.1


def test_no_shifts_means_no_peak():
    assert peak_rolling_window([], CURRENT) is None
