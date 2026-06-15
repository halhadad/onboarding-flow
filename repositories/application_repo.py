import json
import math
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Iterator, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from audit.log import log_status_change, log_integration_check
from config import settings
from services.redaction import redact_integration_payload
from shared.util import now_utc
from domain.ports import ApplicationRepository
from domain.states import ApplicationStatus, CheckOutcome
from db.models import ApplicationRecord, StepResponseRecord, IntegrationLogRecord, DecisionRecord


class ConcurrentModificationError(Exception):
    """Raised when an optimistic concurrency version check fails."""
    pass


class SQLAlchemyApplicationRepository(ApplicationRepository):
    def __init__(self, session: Session):
        self.session = session

    @contextmanager
    def atomic(self) -> Iterator[None]:
        try:
            yield
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _is_expired(self, expires_at: Optional[datetime]) -> bool:
        if expires_at is None:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= now_utc()

    def _context(self, record: ApplicationRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "country": record.country,
            "account_type": record.account_type,
            "status": record.status,
            "version": record.version,
            "resume_token": record.resume_token,
            "resume_token_expires_at": record.resume_token_expires_at,
            "resume_token_expired": self._is_expired(record.resume_token_expires_at),
        }

    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> str:
        token = secrets.token_urlsafe(settings.RESUME_TOKEN_BYTES)
        self.session.add(ApplicationRecord(
            id=application_id,
            country=country.upper(),
            account_type=account_type.lower(),
            status=ApplicationStatus.STARTED.value,
            version=1,
            resume_token=token,
            resume_token_expires_at=now_utc() + timedelta(seconds=settings.RESUME_TOKEN_TTL_SECONDS),
            request_id=request_id,
        ))
        try:
            self.session.flush()
        except IntegrityError as err:
            raise ValueError(f"Application session with ID {application_id} already exists.") from err
        return token

    def get_application_status(self, application_id: str) -> Optional[str]:
        record = self.session.get(ApplicationRecord, application_id)
        return record.status if record else None

    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        record = self.session.get(ApplicationRecord, application_id)
        return self._context(record) if record else None

    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        token = resume_token.strip()
        # token_urlsafe(n) produces ceil(n * 4 / 3) base64url chars (no padding).
        expected_length = math.ceil(settings.RESUME_TOKEN_BYTES * 4 / 3)
        if len(token) != expected_length:
            return None
        record = self.session.execute(
            select(ApplicationRecord).where(ApplicationRecord.resume_token == token)
        ).scalar_one_or_none()
        return self._context(record) if record else None

    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        status_value = ApplicationStatus(status).value
        result = self.session.execute(
            update(ApplicationRecord)
            .where(
                ApplicationRecord.id == application_id,
                ApplicationRecord.version == current_version,
            )
            .values(status=status_value, version=ApplicationRecord.version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise ConcurrentModificationError(
                f"Application {application_id} was modified by another request."
            )

    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        # Stored as entered; the bank reads it back. Encryption at rest is a production concern.
        serialized_data = json.dumps(form_data, sort_keys=True)
        record = self.session.execute(
            select(StepResponseRecord).where(
                StepResponseRecord.application_id == application_id,
                StepResponseRecord.step_id == step_id,
            )
        ).scalar_one_or_none()

        if record:
            record.form_data_json = serialized_data
            record.payload_hash = payload_hash
        else:
            self.session.add(StepResponseRecord(
                application_id=application_id,
                step_id=step_id,
                form_data_json=serialized_data,
                payload_hash=payload_hash,
            ))

        try:
            self.session.flush()
        except IntegrityError as err:
            raise ConcurrentModificationError(
                f"Step '{step_id}' is already being saved by another request."
            ) from err

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        record = self.session.execute(
            select(StepResponseRecord).where(
                StepResponseRecord.application_id == application_id,
                StepResponseRecord.step_id == step_id,
            )
        ).scalar_one_or_none()
        if record:
            return {
                "form_data": json.loads(record.form_data_json),
                "payload_hash": record.payload_hash,
            }
        return None

    def save_decision(self, application_id: str, outcome: str, reasons: list) -> None:
        reasons_json = json.dumps(reasons)
        record = self.session.execute(
            select(DecisionRecord).where(DecisionRecord.application_id == application_id)
        ).scalar_one_or_none()
        if record:
            record.outcome = outcome
            record.reasons_json = reasons_json
        else:
            self.session.add(DecisionRecord(
                application_id=application_id,
                outcome=outcome,
                reasons_json=reasons_json,
            ))

    def log_integration_check(self, application_id: str, service_name: str, status_outcome: CheckOutcome, response_json: str, request_id: str) -> None:
        outcome_value = CheckOutcome(status_outcome).value
        self.session.add(IntegrationLogRecord(
            application_id=application_id,
            service_name=service_name,
            status_outcome=outcome_value,
            raw_response_json=redact_integration_payload(response_json),
            request_id=request_id,
        ))
        log_integration_check(application_id, service_name, outcome_value, request_id)
