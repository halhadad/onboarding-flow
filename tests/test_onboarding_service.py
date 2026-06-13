from typing import Any, Dict, Optional

from integrations.credit import MockCreditBureauService
from integrations.identity import MockIdentityVerificationService
from integrations.bank_account import MockBankAccountService
from integrations.registry import MockRegistryService
from integrations.sanctions import MockSanctionsCheckService
import pytest

from services.onboarding_service import OnboardingService, StateTransitionError
from services.integration_runner import IntegrationUnavailableError


class InMemoryRepository:
    def __init__(self):
        self.status = {"app-1": "STARTED"}
        self.responses = {}
        self.integration_logs = []
        self.decisions = {}
        self.version = 1

    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> None:
        self.status[application_id] = "STARTED"

    def get_application_status(self, application_id: str) -> Optional[str]:
        return self.status.get(application_id)

    def get_application_version(self, application_id: str) -> Optional[int]:
        return self.version if application_id in self.status else None

    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        if application_id not in self.status:
            return None
        return {
            "id": application_id,
            "country": "SWEDEN",
            "account_type": "private",
            "status": self.status[application_id],
            "version": self.version,
        }

    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        self.status[application_id] = status
        self.version += 1

    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        self.responses[(application_id, step_id)] = {"form_data": form_data, "payload_hash": payload_hash}

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        return self.responses.get((application_id, step_id))

    def log_integration_check(self, application_id: str, service_name: str, status_outcome: str, response_json: str, request_id: str) -> None:
        self.integration_logs.append((service_name, status_outcome))

    def save_decision(self, application_id: str, outcome: str, reasons: list) -> None:
        self.decisions[application_id] = (outcome, reasons)


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
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
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

    assert result == {"status": "MANUAL_REVIEW", "next_step_id": None, "reasons": ["bank_account:MANUAL_REVIEW"]}
    assert ("business_credit", "APPROVED") in repository.integration_logs
    assert ("bank_account", "MANUAL_REVIEW") in repository.integration_logs
    assert repository.decisions["app-1"] == ("MANUAL_REVIEW", ["bank_account:MANUAL_REVIEW"])


def test_step_collects_all_reasons_and_takes_the_worst_outcome():
    # business_profile runs business_credit (reject) AND bank_account (review).
    # Both run; all reasons are recorded; the worst outcome (REJECTED) wins.
    repository = InMemoryRepository()
    for step_id in ("business_identity", "representative", "beneficial_owners"):
        repository.responses[("app-1", step_id)] = {"form_data": {}, "payload_hash": f"h-{step_id}"}
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
    )

    result = service.process_step_submission(
        application_id="app-1",
        country="SPAIN",
        account_type="business",
        step_id="business_profile",
        form_data={
            "sector": "RETAIL",
            "annual_turnover": 0.0,
            "expected_monthly_volume": 0.0,
            "iban": "ES9121000418450200059999",
        },
        current_version=1,
        request_id="req-1",
    )

    assert result["status"] == "REJECTED"
    assert result["next_step_id"] is None
    assert set(result["reasons"]) == {"business_credit:REJECTED", "bank_account:MANUAL_REVIEW"}
    assert repository.decisions["app-1"][0] == "REJECTED"


def test_affordability_decision_flows_through_the_engine():
    # Negative disposable income must drive a REJECTED outcome decided by the
    # AutomatedDecisionEngine (the credit mock only reports raw signals).
    repository = InMemoryRepository()
    for step_id in ("collect_identity", "confirm_contact", "regulatory_declarations"):
        repository.responses[("app-1", step_id)] = {"form_data": {}, "payload_hash": f"h-{step_id}"}
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
    )

    result = service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="private",
        step_id="financial_profile",
        form_data={"monthly_income": 1000.0, "monthly_expenses": 1200.0, "outstanding_debts": 0.0},
        current_version=1,
        request_id="req-1",
    )

    assert result == {"status": "REJECTED", "next_step_id": None, "reasons": ["credit_bureau:REJECTED"]}
    assert ("credit_bureau", "REJECTED") in repository.integration_logs
    assert repository.decisions["app-1"] == ("REJECTED", ["credit_bureau:REJECTED"])


def test_transient_provider_failure_does_not_persist_or_manual_review():
    # A provider outage must surface as a transient error, leave the step
    # un-saved (so a retry re-runs it), and never park the application.
    repository = InMemoryRepository()
    for step_id in ("collect_identity", "confirm_contact", "regulatory_declarations"):
        repository.responses[("app-1", step_id)] = {"form_data": {}, "payload_hash": f"h-{step_id}"}

    class FailingCreditService:
        def evaluate(self, *args, **kwargs):
            raise ConnectionError("bureau unreachable")

    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=FailingCreditService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
    )

    with pytest.raises(IntegrationUnavailableError):
        service.process_step_submission(
            application_id="app-1",
            country="SWEDEN",
            account_type="private",
            step_id="financial_profile",
            form_data={"monthly_income": 5000.0, "monthly_expenses": 1000.0, "outstanding_debts": 0.0},
            current_version=1,
            request_id="req-1",
        )

    assert ("app-1", "financial_profile") not in repository.responses
    assert repository.status["app-1"] == "STARTED"
    assert repository.integration_logs == []


def test_service_rejects_step_skipping():
    repository = InMemoryRepository()
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
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


def test_service_short_circuits_idempotent_repeat_submission():
    repository = InMemoryRepository()
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
    )
    form_data = {"personal_identity_number": "199001011234"}
    payload_hash = service._generate_idempotency_key(form_data)
    repository.responses[("app-1", "collect_identity")] = {
        "form_data": {"personal_identity_number": "***1234"},
        "payload_hash": payload_hash,
    }

    result = service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="private",
        step_id="collect_identity",
        form_data=form_data,
        current_version=1,
        request_id="req-1",
    )

    assert result == {"status": "STARTED", "next_step_id": "confirm_contact", "reasons": []}
    assert repository.integration_logs == []


def test_service_rejects_terminal_application_mutation():
    repository = InMemoryRepository()
    repository.status["app-1"] = "APPROVED"
    service = OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
    )

    with pytest.raises(StateTransitionError, match="can no longer be modified"):
        service.process_step_submission(
            application_id="app-1",
            country="SWEDEN",
            account_type="private",
            step_id="collect_identity",
            form_data={"personal_identity_number": "199001011234"},
            current_version=1,
            request_id="req-1",
        )
