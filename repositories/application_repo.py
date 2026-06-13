import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, cast
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from audit.log import SecurityAuditLogger
from domain.ports import ApplicationRepository
from domain.states import ApplicationStatus, CheckOutcome
from db.models import ApplicationRecord, StepResponseRecord, IntegrationLogRecord

class ConcurrentModificationError(Exception):
    """Raised when an optimistic concurrency version check fails."""
    pass

class SQLAlchemyApplicationRepository(ApplicationRepository):
    def __init__(self, session: Session):
        self.session = session

    def _resume_token_expiry(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=7)

    def _is_expired(self, expires_at: Optional[datetime]) -> bool:
        if expires_at is None:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> None:
        record = ApplicationRecord(
            id=application_id,
            country=country.upper(),
            account_type=account_type.lower(),
            status=ApplicationStatus.STARTED.value,
            version=1,
            resume_token=secrets.token_urlsafe(32),
            resume_token_expires_at=self._resume_token_expiry(),
            request_id=request_id 
        )
        try:
            self.session.add(record)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            # Explicitly expunge the failed object from session memory
            self.session.expunge_all() 
            raise ValueError(f"Application session with ID {application_id} already exists.")

    def _redact_form_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        redacted = dict(form_data)
        for key in [
            "personal_identity_number",
            "representative_id",
            "company_identifier",
            "iban",
            "address",
            "phone_number",
        ]:
            if key in redacted:
                value = str(redacted[key])
                redacted[key] = f"***{value[-4:]}" if len(value) >= 4 else "***"
        return redacted

    def _redact_integration_payload(self, response_json: str) -> str:
        sensitive_keys = {
            "personal_identity_number",
            "representative_id",
            "company_identifier",
            "iban",
            "address",
            "phone_number",
            "income",
            "expenses",
            "debts",
            "monthly_income",
            "monthly_expenses",
            "outstanding_debts",
            "tax_residency",
            "is_pep",
        }
        try:
            payload = json.loads(response_json)
        except json.JSONDecodeError:
            return "{}"

        if not isinstance(payload, dict):
            return "{}"

        redacted = {
            key: "***" if key in sensitive_keys else value
            for key, value in payload.items()
        }
        return json.dumps(redacted, sort_keys=True)

    def get_application_status(self, application_id: str) -> Optional[str]:
        record: Any = self.session.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
        return cast(Optional[str], record.status) if record else None

    def get_application_version(self, application_id: str) -> Optional[int]:
        record: Any = self.session.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
        return cast(Optional[int], record.version) if record else None

    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        record: Any = self.session.query(ApplicationRecord).filter(ApplicationRecord.id == application_id).first()
        if not record:
            return None
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

    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        token = resume_token.strip()
        if len(token) < 32 or len(token) > 128:
            return None

        record: Any = self.session.query(ApplicationRecord).filter(
            ApplicationRecord.resume_token == token
        ).first()
        if not record:
            return None
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

    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        status_value = ApplicationStatus(status).value
        updated_rows = self.session.query(ApplicationRecord).filter(
            ApplicationRecord.id == application_id,
            ApplicationRecord.version == current_version
        ).update(
            {
                ApplicationRecord.status: status_value,
                ApplicationRecord.version: ApplicationRecord.version + 1
            },
            synchronize_session=False
        )

        if updated_rows == 0:
            self.session.rollback()
            raise ConcurrentModificationError(
                f"Conflict detected. Application {application_id} was modified by another parallel transaction process."
            )
        
        self.session.commit()

    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        serialized_data = json.dumps(self._redact_form_data(form_data), sort_keys=True)
        record: Any = self.session.query(StepResponseRecord).filter(
            StepResponseRecord.application_id == application_id,
            StepResponseRecord.step_id == step_id
        ).first()

        if record:
            record.form_data_json = serialized_data
            record.payload_hash = payload_hash
        else:
            new_record = StepResponseRecord(
                application_id=application_id,
                step_id=step_id,
                form_data_json=serialized_data,
                payload_hash=payload_hash
            )
            self.session.add(new_record)

        try:
            self.session.commit()
        except IntegrityError as err:
            self.session.rollback()
            raise ConcurrentModificationError(
                f"Idempotency lock triggered. Step {step_id} response is currently processing under an alternative thread environment."
            ) from err

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        record: Any = self.session.query(StepResponseRecord).filter(
            StepResponseRecord.application_id == application_id,
            StepResponseRecord.step_id == step_id
        ).first()
        
        if record:
            return {
                "form_data": json.loads(record.form_data_json),
                "payload_hash": record.payload_hash
            }
        return None

    def log_integration_check(self, application_id: str, service_name: str, status_outcome: CheckOutcome, response_json: str, request_id: str) -> None:
        outcome_value = CheckOutcome(status_outcome).value
        log_entry = IntegrationLogRecord(
            application_id=application_id,
            service_name=service_name,
            status_outcome=outcome_value,
            raw_response_json=self._redact_integration_payload(response_json),
            request_id=request_id
        )
        try:
            self.session.add(log_entry)
            self.session.commit()
            SecurityAuditLogger.log_integration_check(application_id, service_name, outcome_value, request_id)
        except Exception:
            self.session.rollback()
            raise
