from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Job, User
from app.schemas import JobCreate, JobOut, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_owned_job(job_id: int, user: User, db: Session) -> Job:
    job = db.get(Job, job_id)
    # Return 404 (not 403) for other users' jobs so ids can't be probed.
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Job]:
    return list(db.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at)))


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(body: JobCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Job:
    job = Job(user_id=user.id, **body.model_dump())
    db.add(job)
    db.commit()
    return job


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int, body: JobUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Job:
    job = get_owned_job(job_id, user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(get_owned_job(job_id, user, db))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
