from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.states import ApplicationStatus
from shared.util import new_uuid as generate_uuid, now_utc as utc_now


class Base(DeclarativeBase):
    pass


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    country: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=ApplicationStatus.STARTED.value)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resume_token: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, default=generate_uuid)
    resume_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    step_responses: Mapped[List["StepResponseRecord"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    integration_logs: Mapped[List["IntegrationLogRecord"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    decision: Mapped[Optional["DecisionRecord"]] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )


class StepResponseRecord(Base):
    __tablename__ = "step_responses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True, nullable=False)
    step_id: Mapped[str] = mapped_column(String, nullable=False)
    form_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    application: Mapped["ApplicationRecord"] = relationship(back_populates="step_responses")

    __table_args__ = (UniqueConstraint("application_id", "step_id", name="_app_step_uc"),)


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True, index=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    application: Mapped["ApplicationRecord"] = relationship(back_populates="decision")


class IntegrationLogRecord(Base):
    __tablename__ = "integration_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True, nullable=False)
    service_name: Mapped[str] = mapped_column(String, nullable=False)
    status_outcome: Mapped[str] = mapped_column(String, nullable=False)
    raw_response_json: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    application: Mapped["ApplicationRecord"] = relationship(back_populates="integration_logs")

    __table_args__ = (UniqueConstraint("application_id", "service_name", "request_id", name="_app_service_request_uc"),)
