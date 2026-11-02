from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.services.sync import SyncResult, sync_emails

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("")
def run_sync(session: Annotated[Session, Depends(get_session)]) -> SyncResult:
    return sync_emails(session)
