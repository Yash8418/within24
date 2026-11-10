from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobType(str, enum.Enum):
    """How a job counts toward the study permit limit."""

    OFF_CAMPUS = "off_campus"  # counts toward the weekly off-campus limit
    ON_CAMPUS = "on_campus"  # no weekly limit for eligible students
    GIG = "gig"  # off-campus; only time spent earning counts


class ShiftSource(str, enum.Enum):
    MANUAL = "manual"
    CSV_IMPORT = "csv_import"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Toronto")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    jobs: Mapped[list[Job]] = relationship(back_populates="user", cascade="all, delete-orphan")
    breaks: Mapped[list[SchoolBreak]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    employer: Mapped[str | None] = mapped_column(String(120))
    job_type: Mapped[JobType] = mapped_column(Enum(JobType, native_enum=False, length=20))
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(8, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="jobs")
    shifts: Mapped[list[Shift]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="shift_ends_after_start"),
        CheckConstraint("earning_minutes IS NULL OR earning_minutes >= 0", name="earning_minutes_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # For gig work: minutes actually spent earning wages or commission (incl. paid on-call time).
    # When null, the full shift length counts.
    earning_minutes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[ShiftSource] = mapped_column(
        Enum(ShiftSource, native_enum=False, length=20), default=ShiftSource.MANUAL
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="shifts")

    @property
    def counted_minutes(self) -> int:
        """Minutes that count toward work-hour limits."""
        if self.earning_minutes is not None:
            return self.earning_minutes
        return int((self.ends_at - self.starts_at).total_seconds() // 60)


class SchoolBreak(Base):
    """A break in the academic calendar set by the student's school (e.g. winter break, reading week).

    Off-campus hours worked during a scheduled break don't count toward the weekly limit.
    Both dates are inclusive and are interpreted in the user's timezone.
    """

    __tablename__ = "school_breaks"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="break_ends_on_or_after_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="breaks")
