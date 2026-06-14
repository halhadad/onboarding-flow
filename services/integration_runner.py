import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict

from domain.decisioning import (
    AutomatedDecisionEngine,
    BusinessProfile,
    OwnershipProfile,
)
from domain.enums import IntegrationName
from domain.ports import (
    BankAccountValidationService,
    CreditBureauService,
    IdentityVerificationService,
    IntegrationResult,
    RegistryLookupService,
    SanctionsCheckService,
)
from domain.states import CheckOutcome

logger = logging.getLogger("onboarding.integrations")

IntegrationHandler = Callable[[str, Dict[str, Any], str], Awaitable[IntegrationResult]]


class IntegrationUnavailableError(Exception):
    def __init__(self, integration_name: str):
        super().__init__(f"Integration '{integration_name}' is temporarily unavailable.")
        self.integration_name = integration_name


class IntegrationRunner:

    def __init__(
        self,
        identity_service: IdentityVerificationService,
        sanctions_service: SanctionsCheckService,
        credit_service: CreditBureauService,
        registry_service: RegistryLookupService,
        bank_account_service: BankAccountValidationService,
        decision_engine: AutomatedDecisionEngine,
        timeout_seconds: float = 2.0,
        max_attempts: int = 2,
        demo_delay_seconds: float = 0.0,
    ) -> None:
        self.identity_service = identity_service
        self.sanctions_service = sanctions_service
        self.credit_service = credit_service
        self.registry_service = registry_service
        self.bank_account_service = bank_account_service
        self.decision_engine = decision_engine
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.demo_delay_seconds = demo_delay_seconds
        self._handlers: Dict[IntegrationName, IntegrationHandler] = {
            IntegrationName.IDENTITY: self._run_identity_check,
            IntegrationName.ADDRESS_LOOKUP: self._run_address_lookup,
            IntegrationName.SANCTIONS: self._run_sanctions_check,
            IntegrationName.CREDIT_BUREAU: self._run_credit_bureau_check,
            IntegrationName.REGISTRY: self._run_registry_check,
            IntegrationName.REPRESENTATIVE: self._run_representative_check,
            IntegrationName.UBO_KYC: self._run_ubo_kyc_check,
            IntegrationName.BUSINESS_CREDIT: self._run_business_credit_check,
            IntegrationName.BANK_ACCOUNT: self._run_bank_account_check,
        }

    async def run(self, integration_name: str, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        handler = self._handlers.get(IntegrationName(integration_name))
        if handler is None:
            raise ValueError(f"No integration handler registered for '{integration_name}'.")

        if self.demo_delay_seconds > 0:
            await asyncio.sleep(self.demo_delay_seconds)

        log_context = {
            "request_id": request_id,
            "application_id": application_id,
            "integration": str(integration_name),
        }
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await asyncio.wait_for(
                    handler(application_id, form_data, request_id),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                # Transient: retry until attempts are exhausted.
                logger.warning("integration_timeout", extra={**log_context, "attempt": attempt})
            except Exception as exc:
                # Inputs are validated upstream, so a non timeout error is a provider
                # fault. Log metadata only, never the payload or exception text.
                logger.error("integration_call_failed", extra={**log_context, "error_type": type(exc).__name__})
                raise IntegrationUnavailableError(str(integration_name)) from exc

        logger.error("integration_unavailable", extra={**log_context, "attempts": self.max_attempts})
        raise IntegrationUnavailableError(str(integration_name))

    @staticmethod
    def _to_number(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value or "").strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    # Risk checks: gather facts, the engine decides.

    async def _run_credit_bureau_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        assessment = await self.credit_service.evaluate(
            self._to_number(form_data.get("monthly_income")),
            self._to_number(form_data.get("monthly_expenses")),
            self._to_number(form_data.get("outstanding_debts")),
        )
        outcome = self.decision_engine.assess_affordability(assessment)
        payload = {
            "score": assessment.score,
            "disposable_income": assessment.disposable_income,
            "debt_to_income_ratio": assessment.debt_to_income_ratio,
            "debt_flags": list(assessment.flags),
        }
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    async def _run_sanctions_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        screening = await self.sanctions_service.check(
            str(form_data.get("tax_residency", "")),
            bool(form_data.get("is_pep")),
        )
        outcome = self.decision_engine.assess_sanctions(screening)
        payload = {
            "sanctions_hit": screening.sanctions_hit,
            "pep_hit": screening.pep_hit,
            "matched_country": screening.matched_country,
        }
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    async def _run_ubo_kyc_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        profile = OwnershipProfile(
            ubo_count=int(self._to_number(form_data.get("ubo_count"))),
            largest_ownership_percent=self._to_number(form_data.get("largest_ownership_percent")),
        )
        outcome = self.decision_engine.assess_ownership(profile)
        payload = {"ubo_count": profile.ubo_count, "largest_ownership_percent": profile.largest_ownership_percent}
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    async def _run_business_credit_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        profile = BusinessProfile(
            annual_turnover=self._to_number(form_data.get("annual_turnover")),
            expected_monthly_volume=self._to_number(form_data.get("expected_monthly_volume")),
            sector=str(form_data.get("sector", "")),
        )
        outcome = self.decision_engine.assess_business_credit(profile)
        # Log raw figures; downstream reporting buckets them, not this service.
        payload = {
            "annual_turnover": profile.annual_turnover,
            "expected_monthly_volume": profile.expected_monthly_volume,
            "sector": profile.sector,
        }
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    async def _run_representative_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        has_authority = bool(form_data.get("has_signatory_authority"))
        outcome = self.decision_engine.assess_representative_authority(has_authority)
        payload = {"authority": "confirmed" if has_authority else "missing_or_unconfirmed"}
        return IntegrationResult(outcome, json.dumps(payload))

    # Provider authority checks: the external system's own verdict.


    async def _run_identity_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        pin = form_data.get("personal_identity_number") or form_data.get("representative_id", "")
        return await self.identity_service.verify(str(pin))

    async def _run_registry_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return await self.registry_service.lookup_entity(str(form_data.get("company_identifier", "")))

    async def _run_bank_account_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return await self.bank_account_service.validate_iban(str(form_data.get("iban", "")))

    # Low risk checks, engine may not need to check it (Demo)

    _ADDRESS_CONFIDENCE = 0.95

    async def _run_address_lookup(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return IntegrationResult(
            status_outcome=CheckOutcome.APPROVED,
            raw_response_json=json.dumps({"address_confidence": self._ADDRESS_CONFIDENCE, "status": "FETCHED"}),
        )
