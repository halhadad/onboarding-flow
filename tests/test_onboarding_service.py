from contextlib import contextmanager
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

    @contextmanager
    def atomic(self):
        yield

    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> str:
        self.status[application_id] = "STARTED"
        return "token"

    def get_application_status(self, application_id: str) -> Optional[str]:
        return self.status.get(application_id)

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


def _service(repository, credit_service=None):
    return OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=credit_service or MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
    )


async def test_business_profile_runs_bank_account_after_approved_business_credit():
    repository = InMemoryRepository()
    repository.responses[("app-1", "business_identity")] = {"form_data": {}, "payload_hash": "h1"}
    repository.responses[("app-1", "representative")] = {"form_data": {}, "payload_hash": "h2"}
    repository.responses[("app-1", "beneficial_owners")] = {"form_data": {}, "payload_hash": "h3"}
    service = _service(repository)

    result = await service.process_step_submission(
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


async def test_step_collects_all_reasons_and_takes_the_worst_outcome():
    repository = InMemoryRepository()
    for step_id in ("business_identity", "representative", "beneficial_owners"):
        repository.responses[("app-1", step_id)] = {"form_data": {}, "payload_hash": f"h-{step_id}"}
    service = _service(repository)

    result = await service.process_step_submission(
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


async def test_affordability_decision_flows_through_the_engine():
    repository = InMemoryRepository()
    for step_id in ("collect_identity", "confirm_contact", "regulatory_declarations"):
        repository.responses[("app-1", step_id)] = {"form_data": {}, "payload_hash": f"h-{step_id}"}
    service = _service(repository)

    result = await service.process_step_submission(
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


async def test_transient_provider_failure_does_not_persist_or_manual_review():
    repository = InMemoryRepository()
    for step_id in ("collect_identity", "confirm_contact", "regulatory_declarations"):
        repository.responses[("app-1", step_id)] = {"form_data": {}, "payload_hash": f"h-{step_id}"}

    class FailingCreditService:
        async def evaluate(self, *args, **kwargs):
            raise ConnectionError("bureau unreachable")

    service = _service(repository, credit_service=FailingCreditService())

    with pytest.raises(IntegrationUnavailableError):
        await service.process_step_submission(
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


async def test_service_rejects_step_skipping():
    repository = InMemoryRepository()
    service = _service(repository)

    with pytest.raises(StateTransitionError, match="Complete"):
        await service.process_step_submission(
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


async def test_service_short_circuits_idempotent_repeat_submission():
    repository = InMemoryRepository()
    service = _service(repository)
    form_data = {"personal_identity_number": "199001011234"}
    payload_hash = service._payload_fingerprint(form_data)
    repository.responses[("app-1", "collect_identity")] = {
        "form_data": {"personal_identity_number": "***1234"},
        "payload_hash": payload_hash,
    }

    result = await service.process_step_submission(
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


async def test_sweden_business_full_happy_path_reaches_approved():
    repository = InMemoryRepository()
    service = _service(repository)

    await service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="business",
        step_id="business_identity",
        form_data={
            "company_identifier": "5560360793",
            "legal_name": "Acme AB",
            "legal_form": "AB",
        },
        current_version=1,
        request_id="req-1",
    )
    await service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="business",
        step_id="representative",
        form_data={
            "representative_name": "Jane Doe",
            "representative_id": "199001011234",
            "has_signatory_authority": True,
        },
        current_version=1,
        request_id="req-1",
    )
    await service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="business",
        step_id="beneficial_owners",
        form_data={"ubo_count": 2, "largest_ownership_percent": 40.0},
        current_version=1,
        request_id="req-1",
    )
    result = await service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="business",
        step_id="business_profile",
        form_data={
            "sector": "RETAIL",
            "annual_turnover": 100000.0,
            "expected_monthly_volume": 2000.0,
        },
        current_version=1,
        request_id="req-1",
    )

    assert result == {"status": "IN_PROGRESS", "next_step_id": "review_consent", "reasons": []}

    final_result = await service.process_step_submission(
        application_id="app-1",
        country="SWEDEN",
        account_type="business",
        step_id="review_consent",
        form_data={"consent": True},
        current_version=1,
        request_id="req-1",
    )

    assert final_result == {"status": "APPROVED", "next_step_id": None, "reasons": []}
    assert repository.decisions["app-1"] == ("APPROVED", [])


async def test_poland_business_registry_rejection_short_circuits_remaining_steps():
    repository = InMemoryRepository()
    service = _service(repository)

    result = await service.process_step_submission(
        application_id="app-1",
        country="POLAND",
        account_type="business",
        step_id="business_identity",
        form_data={
            "company_identifier": "0099887766",
            "legal_name": "Acme Sp. z o.o.",
            "legal_form": "Sp. z o.o.",
        },
        current_version=1,
        request_id="req-1",
    )

    assert result == {"status": "REJECTED", "next_step_id": None, "reasons": ["registry:REJECTED"]}
    assert ("registry", "REJECTED") in repository.integration_logs
    assert repository.decisions["app-1"] == ("REJECTED", ["registry:REJECTED"])
    assert ("app-1", "representative") not in repository.responses


async def test_service_rejects_terminal_application_mutation():
    repository = InMemoryRepository()
    repository.status["app-1"] = "APPROVED"
    service = _service(repository)

    with pytest.raises(StateTransitionError, match="can no longer be modified"):
        await service.process_step_submission(
            application_id="app-1",
            country="SWEDEN",
            account_type="private",
            step_id="collect_identity",
            form_data={"personal_identity_number": "199001011234"},
            current_version=1,
            request_id="req-1",
        )
