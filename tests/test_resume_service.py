from typing import Any, Dict, Optional

import pytest

from services.resume_service import ResumeApplicationError, ResumeService


class ResumeRepository:
    def __init__(self):
        self.status = {"app-1": "STARTED"}
        self.context_by_token = {
            "valid-token-with-enough-entropy-123456": {
                "id": "app-1",
                "country": "SWEDEN",
                "account_type": "private",
                "status": "STARTED",
                "version": 2,
                "resume_token_expired": False,
            },
            "expired-token-with-enough-entropy-123": {
                "id": "app-1",
                "country": "SWEDEN",
                "account_type": "private",
                "status": "STARTED",
                "version": 2,
                "resume_token_expired": True,
            },
        }
        self.responses = {
            ("app-1", "collect_identity"): {"form_data": {}, "payload_hash": "h1"},
        }

    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> None:
        self.status[application_id] = "STARTED"

    def get_application_status(self, application_id: str) -> Optional[str]:
        return self.status.get(application_id)

    def get_application_version(self, application_id: str) -> Optional[int]:
        return 1

    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        return None

    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        return self.context_by_token.get(resume_token)

    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        self.status[application_id] = status

    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        self.responses[(application_id, step_id)] = {"form_data": form_data, "payload_hash": payload_hash}

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        return self.responses.get((application_id, step_id))

    def log_integration_check(self, application_id: str, service_name: str, status_outcome: str, response_json: str, request_id: str) -> None:
        pass


def test_resume_by_token_returns_first_incomplete_step():
    repository = ResumeRepository()
    service = ResumeService(repository)

    result = service.resume_by_token("valid-token-with-enough-entropy-123456")

    assert result["application_id"] == "app-1"
    assert result["country"] == "SWEDEN"
    assert result["account_type"] == "private"
    assert result["next_step_id"] == "confirm_contact"


def test_resume_by_token_rejects_expired_token():
    service = ResumeService(ResumeRepository())

    with pytest.raises(ResumeApplicationError, match="expired"):
        service.resume_by_token("expired-token-with-enough-entropy-123")


def test_resume_by_token_rejects_application_parked_in_manual_review():
    repository = ResumeRepository()
    repository.status["app-1"] = "MANUAL_REVIEW"
    service = ResumeService(repository)

    with pytest.raises(ResumeApplicationError, match="no longer open for input"):
        service.resume_by_token("valid-token-with-enough-entropy-123456")
