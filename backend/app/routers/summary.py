from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Job, JobType, Shift, User
from app.rules.engine import (
    LIMITED_JOB_TYPES,
    WorkPeriod,
    limited_segments,
    minutes_between,
    peak_rolling_window,
    week_start_for,
    weekly_totals,
)
from app.rules.ruleset import CURRENT, ruleset_for
from app.schemas import as_utc

router = APIRouter(tags=["summary"])


# ---------- Response models ----------
class SourceOut(BaseModel):
    title: str
    url: str
    checked_on: date


class RuleOut(BaseModel):
    id: str
    title: str
    summary: str
    sources: list[SourceOut]


class RulesOut(BaseModel):
    version: str
    effective_from: date
    off_campus_weekly_limit_hours: float
    rules: list[RuleOut]


class WeekOut(BaseModel):
    start: date
    end: date
    minutes: float
    remaining_minutes: float
    limit_minutes: int
    status: str


class RollingOut(BaseModel):
    window_start: datetime
    window_end: datetime
    minutes: float
    status: str


class JobMinutesOut(BaseModel):
    job_id: int
    name: str
    job_type: JobType
    minutes: float
    counts_toward_limit: bool


class RecentWeekOut(BaseModel):
    week_start: date
    minutes: float
    status: str


class SummaryOut(BaseModel):
    rules_version: str
    week: WeekOut
    rolling_peak: RollingOut | None
    by_job: list[JobMinutesOut]
    recent_weeks: list[RecentWeekOut]


# ---------- Helpers ----------
def to_period(shift: Shift) -> WorkPeriod:
    return WorkPeriod(as_utc(shift.starts_at), as_utc(shift.ends_at), shift.counted_minutes, shift.job.job_type)


def load_shifts(db: Session, user: User, start: datetime, end: datetime) -> list[Shift]:
    # A shift can be at most 24 h long, so look back one extra day to catch overnight shifts.
    query = (
        select(Shift)
        .join(Job)
        .where(Job.user_id == user.id, Shift.starts_at >= start - timedelta(days=1), Shift.starts_at < end)
        .order_by(Shift.starts_at)
    )
    return list(db.scalars(query))


# ---------- Endpoints ----------
@router.get("/rules", response_model=RulesOut)
def rules() -> RulesOut:
    return RulesOut(
        version=CURRENT.version,
        effective_from=CURRENT.effective_from,
        off_campus_weekly_limit_hours=CURRENT.off_campus_weekly_limit_hours,
        rules=[
            RuleOut(
                id=r.id,
                title=r.title,
                summary=r.summary,
                sources=[SourceOut(title=s.title, url=s.url, checked_on=s.checked_on) for s in r.sources],
            )
            for r in CURRENT.rules
        ],
    )


@router.get("/summary", response_model=SummaryOut)
def summary(
    day: date | None = Query(default=None, alias="date", description="Any day in the week to summarize"),
    weeks_back: int = Query(default=8, ge=1, le=52),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummaryOut:
    tz = ZoneInfo(user.timezone)
    day = day or datetime.now(timezone.utc).astimezone(tz).date()
    ruleset = ruleset_for(day)
    if ruleset is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Weeks before Nov 8, 2024 aren't supported yet")

    week_start = week_start_for(day, 0)
    week_end = week_start + timedelta(days=6)
    first_week = week_start - timedelta(weeks=weeks_back - 1)
    window_lo = datetime.combine(first_week - timedelta(days=7), datetime.min.time(), tzinfo=tz)
    window_hi = datetime.combine(week_end + timedelta(days=8), datetime.min.time(), tzinfo=tz)

    shifts = load_shifts(db, user, window_lo, window_hi)
    breaks: list = []  # scheduled breaks are added in a later step
    segments = limited_segments([to_period(s) for s in shifts], breaks, tz)

    weeks = weekly_totals(segments, tz, ruleset, first_week, week_end)
    this_week = weeks[-1]

    # Rolling peak among 7-day windows that overlap the selected week.
    week_lo = datetime.combine(week_start, datetime.min.time(), tzinfo=tz)
    week_hi = week_lo + timedelta(days=7)
    nearby = [s for s in segments if s.end > week_lo - timedelta(days=7) and s.start < week_hi + timedelta(days=7)]
    peak = peak_rolling_window(nearby, ruleset)
    if peak and (peak.window_end <= week_lo or peak.window_start >= week_hi):
        peak = None

    by_job: dict[int, JobMinutesOut] = {}
    for shift in shifts:
        period = to_period(shift)
        if period.job_type in LIMITED_JOB_TYPES:
            minutes = minutes_between(limited_segments([period], breaks, tz), week_lo, week_hi)
        else:
            share = (min(period.end, week_hi) - max(period.start, week_lo)) / (period.end - period.start)
            minutes = period.counted_minutes * max(share, 0)
        if minutes <= 0:
            continue
        entry = by_job.setdefault(
            shift.job_id,
            JobMinutesOut(
                job_id=shift.job_id,
                name=shift.job.name,
                job_type=shift.job.job_type,
                minutes=0,
                counts_toward_limit=shift.job.job_type in LIMITED_JOB_TYPES,
            ),
        )
        entry.minutes = round(entry.minutes + minutes, 1)

    return SummaryOut(
        rules_version=ruleset.version,
        week=WeekOut(
            start=week_start,
            end=week_end,
            minutes=this_week.minutes,
            remaining_minutes=round(max(this_week.limit_minutes - this_week.minutes, 0), 1),
            limit_minutes=this_week.limit_minutes,
            status=this_week.status,
        ),
        rolling_peak=RollingOut(**peak.__dict__) if peak else None,
        by_job=sorted(by_job.values(), key=lambda j: -j.minutes),
        recent_weeks=[RecentWeekOut(week_start=w.week_start, minutes=w.minutes, status=w.status) for w in weeks],
    )
