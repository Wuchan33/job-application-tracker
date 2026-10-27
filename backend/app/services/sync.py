import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from google.genai import errors
from sqlmodel import Session, select

from app.models import Application, Email
from app.services.gmail import get_message, get_service, list_message_ids
from app.services.llm import EmailType, classify_email

import logging

logger = logging.getLogger(__name__)

CLOSED_STATUSES = (EmailType.REJECTION, EmailType.OFFER)
OPEN_APPLICATION_DAYS = 120
GMAIL_QUERY = "newer_than:7d -category:promotions -category:social -category:forums"
REQUEST_DELAY_SECONDS = 5


def _get_known_ids(session: Session, gmail_ids: list[str]) -> set[str]:
    if not gmail_ids:
        return set()

    statement = select(Email.gmail_id).where(Email.gmail_id.in_(gmail_ids))
    return set(session.exec(statement).all())


def _find_application_by_thread(session: Session, thread_id: str) -> Application | None:
    statement = (
        select(Application)
        .join(Email, Email.application_id == Application.id)
        .where(Email.thread_id == thread_id)
        .limit(1)
    )
    return session.exec(statement).first()


def _get_open_applications(session: Session) -> list[Application]:
    since = datetime.now(UTC) - timedelta(days=OPEN_APPLICATION_DAYS)
    statement = (
        select(Application)
        .where(Application.status.not_in(CLOSED_STATUSES))
        .where(Application.applied_at >= since)
        .order_by(Application.applied_at.desc())
    )
    return list(session.exec(statement).all())


def _format_applications(applications: list[Application]) -> str:
    if not applications:
        return "(none)"

    return "\n".join(
        f"[{a.id}] {a.company} - {a.position or 'unknown position'} "
        f"(applied) {a.applied_at:%Y-%m-%d})"
        for a in applications
    )


def _process_email(session: Session, service, msg_id: str) -> None:
    email = get_message(service, msg_id)
    text = f"Subject: {email.subject}\n From: {email.sender}\n\n{email.body}"

    application = _find_application_by_thread(session, email.thread_id)

    if application:
        result = classify_email(text)
    else:
        open_apps = _get_open_applications(session)
        result = classify_email(text, _format_applications(open_apps))

        if result.is_recruitment:
            open_ids = {a.id: a for a in open_apps}
            application = open_ids.get(result.application_id)

            if application is None:
                application = Application(
                    company=result.company or "Unknown",
                    position=result.position,
                    status=result.type,
                    applied_at=email.date,
                    updated_at=email.date,
                )
                session.add(application)
                session.flush()

    if application and result.type != EmailType.OTHER:
        application.status = result.type
        application.updated_at = email.date
        if application.position is None:
            application.position = result.position

    session.add(
        Email(
            gmail_id=email.gmail_id,
            thread_id=email.thread_id,
            sender=email.sender,
            subject=email.subject,
            received_at=email.date,
            type=result.type,
            application_id=application.id if application else None,
        )
    )


@dataclass
class SyncResult:
    processed: int = 0
    failed: int = 0
    stopped_early: bool = False


def sync_emails(session: Session) -> SyncResult:
    service = get_service()
    gmail_ids = list_message_ids(service, GMAIL_QUERY)
    known = _get_known_ids(session, gmail_ids)
    new_ids = [i for i in reversed(gmail_ids) if i not in known]

    result = SyncResult()
    for msg_id in new_ids:
        try:
            _process_email(session, service, msg_id)
            session.commit()
            result.processed += 1
        except errors.APIError as e:
            session.rollback()
            logger.warning("Gemini unavailable, stopping sync: %s", e)
            result.stopped_early = True
            break
        except Exception:
            session.rollback()
            logger.exception("Failed to process email %s", msg_id)
            result.failed += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return result

if __name__ == "__main__":
    from app.db import engine

    logging.basicConfig(level=logging.INFO)
    with Session(engine) as session:
        print(sync_emails(session))