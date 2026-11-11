from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.rules.engine import week_start_for
from app.rules.ruleset import ruleset_for
from app.services.hours import load_breaks, load_shifts, local_midnight
from app.services.report import build_hours_pdf

router = APIRouter(prefix="/reports", tags=["reports"])

MAX_WEEKS = 53


@router.get("/hours.pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def hours_pdf(
    start: date | None = Query(default=None, description="First day to include (default: 12 weeks ago)"),
    end: date | None = Query(default=None, description="Last day to include (default: today)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    tz = ZoneInfo(user.timezone)
    today = datetime.now(timezone.utc).astimezone(tz).date()
    end = end or today
    start = start or end - timedelta(weeks=12) + timedelta(days=1)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "'start' must be on or before 'end'")
    first_week = week_start_for(start, 0)
    if (end - first_week).days >= MAX_WEEKS * 7:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A report can cover at most one year")
    ruleset = ruleset_for(first_week)
    if ruleset is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Weeks before Nov 8, 2024 aren't supported yet")

    last_day = week_start_for(end, 0) + timedelta(days=6)  # whole weeks only
    lo, hi = local_midnight(first_week - timedelta(days=7), tz), local_midnight(last_day + timedelta(days=8), tz)
    shifts = load_shifts(db, user, lo, hi)
    school_breaks = load_breaks(db, user, lo.date(), hi.date())
    pdf = build_hours_pdf(user, shifts, school_breaks, ruleset, first_week, last_day)
    filename = f"within24-hours-{first_week}-to-{last_day}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
