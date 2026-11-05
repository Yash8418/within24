from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Job, JobType, Shift, User


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_job(db, job_type=JobType.OFF_CAMPUS):
    user = User(email="student@example.com", hashed_password="x")
    job = Job(user=user, name="Cashier", employer="Grocery store", job_type=job_type)
    db.add(job)
    db.commit()
    return job


START = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)


def test_full_shift_length_counts_by_default(db):
    job = make_job(db)
    shift = Shift(job=job, starts_at=START, ends_at=START + timedelta(hours=6, minutes=30))
    db.add(shift)
    db.commit()
    assert shift.counted_minutes == 390


def test_gig_shift_counts_only_earning_time(db):
    job = make_job(db, JobType.GIG)
    shift = Shift(job=job, starts_at=START, ends_at=START + timedelta(hours=5), earning_minutes=120)
    db.add(shift)
    db.commit()
    assert shift.counted_minutes == 120


def test_shift_must_end_after_it_starts(db):
    job = make_job(db)
    db.add(Shift(job=job, starts_at=START, ends_at=START - timedelta(hours=1)))
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_a_user_removes_their_jobs_and_shifts(db):
    job = make_job(db)
    db.add(Shift(job=job, starts_at=START, ends_at=START + timedelta(hours=4)))
    db.commit()
    db.delete(job.user)
    db.commit()
    assert db.query(Job).count() == 0
    assert db.query(Shift).count() == 0
