from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import JobType, ShiftSource


def as_utc(value: datetime) -> datetime:
    """SQLite drops timezone info; treat stored naive datetimes as UTC."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def to_utc(value: datetime) -> datetime:
    """Convert an instant to UTC before comparing it with stored datetimes (naive values are taken as UTC)."""
    return as_utc(value).astimezone(timezone.utc)


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    timezone: str = "America/Toronto"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    timezone: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Jobs ----------
class JobBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    employer: str | None = Field(default=None, max_length=120)
    job_type: JobType
    hourly_rate: float | None = Field(default=None, ge=0)


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    employer: str | None = Field(default=None, max_length=120)
    job_type: JobType | None = None
    hourly_rate: float | None = Field(default=None, ge=0)


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------- Shifts ----------
class ShiftBase(BaseModel):
    starts_at: datetime
    ends_at: datetime
    earning_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must include a timezone offset, e.g. 2026-11-05T09:00:00-05:00")
        # Store every instant in UTC. SQLite keeps only the wall-clock part of a datetime,
        # so an offset like -05:00 would otherwise be lost on save.
        return to_utc(value)

    @model_validator(mode="after")
    def check_times(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.ends_at - self.starts_at > timedelta(hours=24):
            raise ValueError("a single shift can't be longer than 24 hours")
        length = int((self.ends_at - self.starts_at).total_seconds() // 60)
        if self.earning_minutes is not None and self.earning_minutes > length:
            raise ValueError("earning_minutes can't be longer than the shift itself")
        return self


class ShiftCreate(ShiftBase):
    job_id: int


class ShiftUpdate(ShiftBase):
    job_id: int


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    starts_at: datetime
    ends_at: datetime
    earning_minutes: int | None
    counted_minutes: int
    notes: str | None
    source: ShiftSource

    @field_validator("starts_at", "ends_at")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return as_utc(value)


class BreakBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("The break must end on or after its start date")
        if (self.end_date - self.start_date).days > 183:
            raise ValueError("A break can be at most 6 months long")
        return self


class BreakCreate(BreakBase):
    pass


class BreakOut(BreakBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ImportIn(BaseModel):
    job_id: int
    csv: str = Field(min_length=1, max_length=1_000_000)
    dry_run: bool = True


class ImportRowOut(BaseModel):
    line: int
    starts_at: datetime
    ends_at: datetime
    earning_minutes: int | None
    notes: str | None
    duplicate: bool  # already saved for this job (or repeated in the file); skipped on import


class RowErrorOut(BaseModel):
    line: int
    message: str


class ImportOut(BaseModel):
    rows: list[ImportRowOut]
    errors: list[RowErrorOut]
    imported: int
    dry_run: bool
