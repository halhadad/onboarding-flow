import pytest

from domain.decisioning import AutomatedDecisionEngine
from domain.enums import IntegrationName
from integrations.bank_account import MockBankAccountService
from integrations.credit import MockCreditBureauService
from integrations.identity import MockIdentityVerificationService
from integrations.registry import MockRegistryService
from integrations.sanctions import MockSanctionsCheckService
from services.integration_runner import IntegrationRunner, IntegrationUnavailableError


def _runner(**kwargs) -> IntegrationRunner:
    return IntegrationRunner(
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
        decision_engine=AutomatedDecisionEngine(),
        **kwargs,
    )


async def test_unreachable_provider_times_out_and_is_reported_unavailable():
    # IBAN ending in 0000 makes the mock hang; the short timeout and retries
    # are exhausted, surfacing a transient failure rather than hanging.
    runner = _runner(timeout_seconds=0.01, max_attempts=2)

    with pytest.raises(IntegrationUnavailableError):
        await runner.run(IntegrationName.BANK_ACCOUNT, "app-1", {"iban": "ES0000"}, "req-1")


async def test_healthy_provider_returns_its_outcome():
    runner = _runner(timeout_seconds=1.0, max_attempts=2)

    result = await runner.run(
        IntegrationName.BANK_ACCOUNT, "app-1", {"iban": "ES9121000418450200051332"}, "req-1"
    )

    assert result.status_outcome == "APPROVED"
