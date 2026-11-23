from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class EmailType(StrEnum):
    APPLIED = "applied"
    ONLINE_ASSESSMENT = "online_assessment"
    HR_INTERVIEW = "hr_interview"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTION = "rejection"
    OTHER = "other"


def _enum_column(**kwargs) -> Column:
    return Column(
        SAEnum(
            EmailType,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda e: [m.value for m in e],
            length=32,
        ),
        **kwargs,
    )


class Application(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company: str
    position: str | None = None
    status: EmailType = Field(default=EmailType.APPLIED, sa_column=_enum_column(nullable=False))
    applied_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class Email(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    gmail_id: str = Field(unique=True)
    thread_id: str
    received_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    type: EmailType = Field(sa_column=_enum_column(nullable=False))
    application_id: int | None = Field(default=None, foreign_key="application.id")


class SyncRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
