from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Job, Shift, ShiftSource, User
from app.routers.jobs import get_owned_job
from app.schemas import ImportIn, ImportOut, ImportRowOut, RowErrorOut, ShiftCreate, ShiftOut, ShiftUpdate, to_utc
from app.services.csv_import import parse_shifts_csv

router = APIRouter(prefix="/shifts", tags=["shifts"])


def get_owned_shift(shift_id: int, user: User, db: Session) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None or shift.job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shift not found")
    return shift


@router.get("", response_model=list[ShiftOut])
def list_shifts(
    start: datetime | None = Query(default=None, description="Only shifts starting at or after this time"),
    end: datetime | None = Query(default=None, description="Only shifts starting before this time"),
    job_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Shift]:
    query = select(Shift).join(Job).where(Job.user_id == user.id)
    if start is not None:
        query = query.where(Shift.starts_at >= to_utc(start))
    if end is not None:
        query = query.where(Shift.starts_at < to_utc(end))
    if job_id is not None:
        query = query.where(Shift.job_id == job_id)
    return list(db.scalars(query.order_by(Shift.starts_at)))


@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def create_shift(body: ShiftCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Shift:
    get_owned_job(body.job_id, user, db)
    shift = Shift(**body.model_dump())
    db.add(shift)
    db.commit()
    return shift


@router.post("/import", response_model=ImportOut)
def import_shifts(body: ImportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ImportOut:
    """Import shifts from CSV text. Nothing is saved if any row has an error (or when dry_run is true)."""
    job = get_owned_job(body.job_id, user, db)
    parsed = parse_shifts_csv(body.csv, user.timezone)

    existing = {
        (to_utc(s.starts_at), to_utc(s.ends_at))
        for s in db.scalars(select(Shift).where(Shift.job_id == job.id))
    }
    rows, seen = [], set()
    for shift in parsed.shifts:
        key = (shift.starts_at, shift.ends_at)
        rows.append(
            ImportRowOut(
                line=shift.line,
                starts_at=shift.starts_at,
                ends_at=shift.ends_at,
                earning_minutes=shift.earning_minutes,
                notes=shift.notes,
                duplicate=key in existing or key in seen,
            )
        )
        seen.add(key)

    errors = [RowErrorOut(line=line, message=message) for line, message in parsed.errors]
    new_rows = [row for row in rows if not row.duplicate]
    imported = 0
    if not body.dry_run and not errors and new_rows:
        for row in new_rows:
            db.add(
                Shift(
                    job_id=job.id,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    earning_minutes=row.earning_minutes,
                    notes=row.notes,
                    source=ShiftSource.CSV_IMPORT,
                )
            )
        db.commit()
        imported = len(new_rows)
    return ImportOut(rows=rows, errors=errors, imported=imported, dry_run=body.dry_run)


@router.put("/{shift_id}", response_model=ShiftOut)
def update_shift(
    shift_id: int, body: ShiftUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Shift:
    shift = get_owned_shift(shift_id, user, db)
    get_owned_job(body.job_id, user, db)
    for field, value in body.model_dump().items():
        setattr(shift, field, value)
    db.commit()
    return shift


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(shift_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(get_owned_shift(shift_id, user, db))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
