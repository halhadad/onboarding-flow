from typing import Any, Dict, Optional

from integrations.credit import MockCreditBureauService
from integrations.identity import MockIdentityVerificationService
from integrations.sanctions import MockSanctionsCheckService
import pytest

from services.onboarding_service import OnboardingService, StateTransitionError


class InMemoryRepository:
    def __init__(self):
        self.status = {"app-1": "STARTED"}
        self.responses = {}
        self.integration_logs = []
        self.version = 1

    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> None:
        self.status[application_id] = "STARTED"

    def get_application_status(self, application_id: str) -> Optional[str]:
        return self.status.get(application_id)

    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        self.status[application_id] = status
        self.version += 1

    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        self.responses[(application_id, step_id)] = {"form_data": form_data, "payload_hash": payload_hash}

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        return self.responses.get((application_id, step_id))

    def log_integration_check(self, application_id: str, service_name: str, status_outcome: str, response_json: str, request_id: str) -> None:
        self.integration_logs.append((service_name, status_outcome))


def test_business_profile_runs_bank_account_after_approved_business_credit():
    repository = InMemoryRepository()
    repository.responses[("app-1", "business_identity")] = {"form_data": {}, "payload_hash": "h1"}
    repository.responses[("app-1", "representative")] = {"form_data": {}, "payload_hash": "h2"}
    repository.responses[("app-1", "beneficial_owners")] = {"form_data": {}, "payload_hash": "h3"}
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
    )

    result = service.process_step_submission(
        application_id="app-1",
        country="SPAIN",
        account_type="business",
        step_id="business_profile",
        form_data={
            "sector": "RETAIL",
            "annual_turnover": 100000.0,
            "expected_monthly_volume": 2000.0,
            "iban": "ES9121000418450200059999",
        },
        current_version=1,
        request_id="req-1",
    )

    assert result == {"status": "MANUAL_REVIEW", "next_step_id": None}
    assert ("business_credit", "APPROVED") in repository.integration_logs
    assert ("bank_account", "MANUAL_REVIEW") in repository.integration_logs


def test_service_rejects_step_skipping():
    repository = InMemoryRepository()
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
    )

    with pytest.raises(StateTransitionError, match="cannot be submitted"):
        service.process_step_submission(
            application_id="app-1",
            country="SWEDEN",
            account_type="private",
            step_id="financial_profile",
            form_data={
                "monthly_income": 5000.0,
                "monthly_expenses": 1000.0,
                "outstanding_debts": 0.0,
            },
            current_version=1,
            request_id="req-1",
        )
