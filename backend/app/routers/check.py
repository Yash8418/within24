"""'Can I take this shift?' — run the rules engine with a proposed shift before saving it."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.routers.jobs import get_owned_job
from app.rules.engine import (
    LIMITED_JOB_TYPES,
    WorkPeriod,
    limited_segments,
    minutes_between,
    peak_rolling_window,
)
from app.rules.ruleset import ruleset_for
from app.schemas import ShiftCreate
from app.services.hours import load_shifts, to_period, week_bounds

router = APIRouter(tags=["summary"])

WINDOW = timedelta(days=7)


class WeekImpact(BaseModel):
    week_start: date
    minutes_before: float
    minutes_after: float
    limit_minutes: int
    status_after: str


class CheckShiftOut(BaseModel):
    allowed: bool
    counts_toward_limit: bool
    counted_minutes: float
    weeks: list[WeekImpact]
    rolling_peak_minutes_after: float
    rolling_peak_status_after: str
    message: str


def _status(minutes: float, limit: int, threshold: float) -> str:
    if minutes > limit + 1e-6:
        return "over"
    return "warning" if minutes >= limit * threshold else "ok"


def _hours(minutes: float) -> str:
    return f"{minutes / 60:g}"


class CheckShiftIn(ShiftCreate):
    # When editing an existing shift, leave it out of the "before" picture.
    replaces_shift_id: int | None = None


@router.post("/check-shift", response_model=CheckShiftOut)
def check_shift(body: CheckShiftIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = get_owned_job(body.job_id, user, db)
    tz = ZoneInfo(user.timezone)
    start_local = body.starts_at.astimezone(tz)
    ruleset = ruleset_for(start_local.date())
    if ruleset is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Dates before Nov 8, 2024 aren't supported yet")

    length = int((body.ends_at - body.starts_at).total_seconds() // 60)
    proposed = WorkPeriod(
        body.starts_at, body.ends_at, body.earning_minutes if body.earning_minutes is not None else length, job.job_type
    )
    breaks: list = []  # scheduled breaks are added in a later step
    existing = [to_period(s) for s in load_shifts(db, user, body.starts_at - WINDOW, body.ends_at + WINDOW,
                                                  exclude_id=body.replaces_shift_id)]
    before = limited_segments(existing, breaks, tz)
    after = limited_segments([*existing, proposed], breaks, tz)
    counted = round(sum(s.minutes for s in limited_segments([proposed], breaks, tz)), 1)
    limit, threshold = ruleset.weekly_limit_minutes, ruleset.warning_threshold

    # Every calendar week the shift touches (an overnight shift can span two).
    weeks, day = [], start_local.date()
    while True:
        week_start, lo, hi = week_bounds(day, tz)
        if lo >= body.ends_at:
            break
        minutes_after = round(minutes_between(after, lo, hi), 1)
        weeks.append(
            WeekImpact(
                week_start=week_start,
                minutes_before=round(minutes_between(before, lo, hi), 1),
                minutes_after=minutes_after,
                limit_minutes=limit,
                status_after=_status(minutes_after, limit, threshold),
            )
        )
        day = week_start + timedelta(days=7)

    # Busiest rolling 7-day window that includes any part of the proposed shift.
    nearby = [s for s in after if s.end > body.starts_at - WINDOW and s.start < body.ends_at + WINDOW]
    peak = peak_rolling_window(nearby, ruleset)
    peak_minutes = peak.minutes if peak else 0.0
    peak_status = _status(peak_minutes, limit, threshold)

    counts = job.job_type in LIMITED_JOB_TYPES
    allowed = all(w.status_after != "over" for w in weeks) and peak_status != "over"
    week = weeks[0]
    if not counts:
        message = "On-campus work doesn't count toward the 24-hour off-campus limit."
    elif counted == 0:
        message = "This shift falls in a scheduled break, so it doesn't count toward the weekly limit."
    elif not allowed:
        worst = max([w.minutes_after for w in weeks] + [peak_minutes])
        message = (
            f"Taking this shift would put you at {_hours(worst)} hours in a 7-day period — "
            f"over the {_hours(limit)}-hour limit."
        )
    else:
        message = (
            f"You can take this shift. You'd be at {_hours(week.minutes_after)} of {_hours(limit)} hours "
            f"for the week of {week.week_start:%b} {week.week_start.day}."
        )

    return CheckShiftOut(
        allowed=allowed,
        counts_toward_limit=counts,
        counted_minutes=counted,
        weeks=weeks,
        rolling_peak_minutes_after=peak_minutes,
        rolling_peak_status_after=peak_status,
        message=message,
    )
