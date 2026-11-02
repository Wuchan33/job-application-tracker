from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.services.stats import Period, count_by_period, count_by_status, get_cumulative, get_sankey

router = APIRouter(prefix="/api/stats", tags=["stats"])

DEFAULT_WEEKS = 8


def date_range(
    date_from: datetime | None = None, date_to: datetime | None = None
) -> tuple[datetime, datetime]:
    if date_to is None:
        date_to = datetime.now(UTC)
    if date_from is None:
        date_from = date_to - timedelta(weeks=DEFAULT_WEEKS)
    return date_from, date_to


SessionDep = Annotated[Session, Depends(get_session)]
DateRange = Annotated[tuple[datetime, datetime], Depends(date_range)]


@router.get("/by-status")
def by_status(session: SessionDep, dates: DateRange) -> dict[str, int]:
    return count_by_status(session, *dates)


@router.get("/timeline")
def timeline(session: SessionDep, dates: DateRange, period: Period = "week") -> list[dict]:
    return count_by_period(session, *dates, period)


@router.get("/cumulative")
def cumulative(session: SessionDep, dates: DateRange) -> list[dict]:
    return get_cumulative(session, *dates)


@router.get("/sankey")
def sankey(session: SessionDep, dates: DateRange) -> dict:
    return get_sankey(session, *dates)
