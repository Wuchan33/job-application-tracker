from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Application
from app.services.stats import GHOSTED_AFTER_DAYS
from app.services.sync import CLOSED_STATUSES

router = APIRouter(prefix="/api/applications", tags=["applications"])

@router.get("")
def list_applications(
    session: Annotated[Session, Depends(get_session)], active: bool = False
) -> list[Application]:
    statement = select(Application).order_by(Application.updated_at.desc())
    if active:
        since = datetime.now(UTC) - timedelta(days=GHOSTED_AFTER_DAYS)
        statement = statement.where(
            Application.status.not_in(CLOSED_STATUSES),
            Application.updated_at >= since,
        )
    return list(session.exec(statement).all())


@router.get("/{application_id}")
def get_application(
    session: Annotated[Session, Depends(get_session)], application_id: int
) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application



