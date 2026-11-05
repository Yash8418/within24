from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Job, Shift, User
from app.routers.jobs import get_owned_job
from app.schemas import ShiftCreate, ShiftOut, ShiftUpdate

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
        query = query.where(Shift.starts_at >= start)
    if end is not None:
        query = query.where(Shift.starts_at < end)
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
