"""Shared helpers for turning stored shifts into engine inputs."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, SchoolBreak, Shift, User
from app.rules.engine import Break, WorkPeriod, week_start_for
from app.schemas import as_utc, to_utc

# A single shift is at most 24 hours long (enforced by the API).
MAX_SHIFT = timedelta(days=1)


def to_period(shift: Shift) -> WorkPeriod:
    return WorkPeriod(as_utc(shift.starts_at), as_utc(shift.ends_at), shift.counted_minutes, shift.job.job_type)


def load_shifts(db: Session, user: User, start: datetime, end: datetime, exclude_id: int | None = None) -> list[Shift]:
    """The user's shifts overlapping [start, end)."""
    query = (
        select(Shift)
        .join(Job)
        .where(Job.user_id == user.id, Shift.starts_at >= to_utc(start - MAX_SHIFT), Shift.starts_at < to_utc(end))
        .order_by(Shift.starts_at)
    )
    if exclude_id is not None:
        query = query.where(Shift.id != exclude_id)
    return list(db.scalars(query))


def load_breaks(db: Session, user: User, start: date, end: date) -> list[SchoolBreak]:
    """The user's scheduled breaks that overlap the dates [start, end] (inclusive)."""
    query = (
        select(SchoolBreak)
        .where(SchoolBreak.user_id == user.id, SchoolBreak.start_date <= end, SchoolBreak.end_date >= start)
        .order_by(SchoolBreak.start_date)
    )
    return list(db.scalars(query))


def to_break(school_break: SchoolBreak) -> Break:
    return Break(school_break.start_date, school_break.end_date)


def local_midnight(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


def week_bounds(day: date, tz: ZoneInfo, week_starts_on: int = 0) -> tuple[date, datetime, datetime]:
    """(first day of the week, start instant, end instant) for the week containing `day`."""
    start_day = week_start_for(day, week_starts_on)
    return start_day, local_midnight(start_day, tz), local_midnight(start_day + timedelta(days=7), tz)
