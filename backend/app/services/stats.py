from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Literal

from sqlmodel import Session, func, select

from app.models import Application, Email
from app.services.llm import EmailType

GHOSTED_AFTER_DAYS = 30
Period = Literal["day", "week", "month"]
GROUP_ORDER = ["applied", "screening", "technical", "offer", "rejection"]
CLOSED_GROUPS = ("offer", "rejection")
LINES = tuple(t.value for t in EmailType if t != EmailType.OTHER)

STAGE_GROUPS = {
    EmailType.APPLIED: "applied",
    EmailType.ONLINE_ASSESSMENT: "screening",
    EmailType.HR_INTERVIEW: "screening",
    EmailType.INTERVIEW: "technical",
    EmailType.OFFER: "offer",
    EmailType.REJECTION: "rejection",
}


def count_by_status(session: Session, date_from: datetime, date_to: datetime) -> dict[str, int]:
    statement = (
        select(Application.status, func.count())
        .where(Application.applied_at >= date_from, Application.applied_at < date_to)
        .group_by(Application.status)
    )
    return {status: count for status, count in session.exec(statement).all()}


def count_by_period(
    session: Session, date_from: datetime, date_to: datetime, period: Period
) -> list[dict]:
    bucket = func.date_trunc(period, Application.applied_at).label("bucket")
    statement = (
        select(bucket, Application.status, func.count())
        .where(Application.applied_at >= date_from, Application.applied_at < date_to)
        .group_by(bucket, Application.status)
        .order_by(bucket)
    )
    periods: dict[str, dict] = {}
    for b, status, count in session.exec(statement).all():
        key = b.date().isoformat()
        periods.setdefault(key, {"period": key})[status] = count
    return list(periods.values())


def _get_application_paths(
    session: Session, date_from: datetime, date_to: datetime
) -> dict[int, list[str]]:
    statement = (
        select(Email.application_id, Email.type, Application.updated_at)
        .join(Application, Application.id == Email.application_id)
        .where(
            Application.applied_at >= date_from,
            Application.applied_at < date_to,
            Email.type != EmailType.OTHER,
        )
        .order_by(Email.application_id, Email.received_at)
    )
    paths: dict[int, list[str]] = {}
    last_updated: dict[int, datetime] = {}
    for application_id, email_type, updated_at in session.exec(statement).all():
        stage = STAGE_GROUPS[email_type]
        path = paths.setdefault(application_id, ["applied"])
        if GROUP_ORDER.index(stage) > GROUP_ORDER.index(path[-1]):
            path.append(stage)
        last_updated[application_id] = updated_at

    ghosted_before = datetime.now(UTC) - timedelta(days=GHOSTED_AFTER_DAYS)
    for application_id, p in paths.items():
        if p[-1] not in CLOSED_GROUPS and last_updated[application_id] < ghosted_before:
            p.append("ghosted")
    return paths


def get_sankey(session: Session, date_from: datetime, date_to: datetime) -> dict:
    links: Counter[tuple[str, str]] = Counter()
    for path in _get_application_paths(session, date_from, date_to).values():
        for source, target in pairwise(path):
            links[(source, target)] += 1

    nodes = list(dict.fromkeys(name for pair in links for name in pair))
    index = {name: i for i, name in enumerate(nodes)}
    return {
        "nodes": [{"name": name} for name in nodes],
        "links": [
            {"source": index[s], "target": index[t], "value": count}
            for (s, t), count in links.items()
        ],
    }


def _first_reached(
    session: Session, date_from: datetime, date_to: datetime
) -> dict[tuple[int, str], date]:
    statement = (
        select(Email.application_id, Email.type, func.min(Email.received_at))
        .where(
            Email.received_at >= date_from,
            Email.received_at < date_to,
            Email.application_id.is_not(None),
            Email.type.not_in((EmailType.APPLIED, EmailType.OTHER)),
        )
        .group_by(Email.application_id, Email.type)
    )
    return {
        (application_id, email_type): received_at.date()
        for application_id, email_type, received_at in session.exec(statement).all()
    }


def get_cumulative(session: Session, date_from: datetime, date_to: datetime) -> list[dict]:
    daily: defaultdict[date, Counter[str]] = defaultdict(Counter)
    for (_, line), day in _first_reached(session, date_from, date_to).items():
        daily[day][line] += 1

    applied_day = func.date(Application.applied_at).label("day")
    statement = (
        select(applied_day, func.count())
        .where(Application.applied_at >= date_from, Application.applied_at < date_to)
        .group_by(applied_day)
    )
    for day, count in session.exec(statement).all():
        daily[day]["applied"] += count

    totals = dict.fromkeys(LINES, 0)
    result = []
    for day in sorted(daily):
        for line, count in daily[day].items():
            totals[line] += count
        result.append({"day": day.isoformat(), **totals})
    return result
