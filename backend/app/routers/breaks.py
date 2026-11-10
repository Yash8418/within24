from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import SchoolBreak, User
from app.schemas import BreakCreate, BreakOut

router = APIRouter(prefix="/breaks", tags=["breaks"])


def get_owned_break(break_id: int, user: User, db: Session) -> SchoolBreak:
    school_break = db.get(SchoolBreak, break_id)
    if school_break is None or school_break.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Break not found")
    return school_break


@router.get("", response_model=list[BreakOut])
def list_breaks(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SchoolBreak]:
    query = select(SchoolBreak).where(SchoolBreak.user_id == user.id).order_by(SchoolBreak.start_date)
    return list(db.scalars(query))


@router.post("", response_model=BreakOut, status_code=status.HTTP_201_CREATED)
def create_break(body: BreakCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    school_break = SchoolBreak(user_id=user.id, **body.model_dump())
    db.add(school_break)
    db.commit()
    return school_break


@router.put("/{break_id}", response_model=BreakOut)
def update_break(
    break_id: int, body: BreakCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    school_break = get_owned_break(break_id, user, db)
    for field, value in body.model_dump().items():
        setattr(school_break, field, value)
    db.commit()
    return school_break


@router.delete("/{break_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_break(break_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(get_owned_break(break_id, user, db))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
