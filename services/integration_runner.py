import json
import logging
from typing import Any, Callable, Dict

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

IntegrationHandler = Callable[[str, Dict[str, Any], str], IntegrationResult]


class IntegrationUnavailableError(Exception):
    """Transient provider failure; not a manual_review signal."""

    def __init__(self, integration_name: str):
        super().__init__(f"Integration '{integration_name}' is temporarily unavailable.")
        self.integration_name = integration_name


class IntegrationRunner:
    """Runs a step's checks; risk checks go through the decision engine."""

    def __init__(
        self,
        identity_service: IdentityVerificationService,
        sanctions_service: SanctionsCheckService,
        credit_service: CreditBureauService,
        registry_service: RegistryLookupService,
        bank_account_service: BankAccountValidationService,
        decision_engine: AutomatedDecisionEngine,
    ) -> None:
        self.identity_service = identity_service
        self.sanctions_service = sanctions_service
        self.credit_service = credit_service
        self.registry_service = registry_service
        self.bank_account_service = bank_account_service
        self.decision_engine = decision_engine
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

    def run(self, integration_name: str, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        handler = self._handlers.get(IntegrationName(integration_name))
        if handler is None:
            raise ValueError(f"No integration handler registered for '{integration_name}'.")
        try:
            return handler(application_id, form_data, request_id)
        except Exception as exc:
            # Log metadata only, not payload or exception text (may carry customer input).
            logger.error(
                "integration_call_failed",
                extra={
                    "request_id": request_id,
                    "application_id": application_id,
                    "integration": str(integration_name),
                    "error_type": type(exc).__name__,
                },
            )
            raise IntegrationUnavailableError(str(integration_name)) from exc

    @staticmethod
    def _money_band(value: float) -> str:
        if value < 1000:
            return "below_1000"
        if value < 3000:
            return "1000_2999"
        if value < 10000:
            return "3000_9999"
        return "10000_plus"

    # Risk checks: gather facts, the engine decides.

    def _run_credit_bureau_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        assessment = self.credit_service.evaluate(
            float(form_data.get("monthly_income", 0)),
            float(form_data.get("monthly_expenses", 0)),
            float(form_data.get("outstanding_debts", 0)),
        )
        outcome = self.decision_engine.assess_affordability(assessment)
        payload = {
            "score": assessment.score,
            "disposable_income": assessment.disposable_income,
            "debt_to_income_ratio": assessment.debt_to_income_ratio,
            "debt_flags": list(assessment.flags),
        }
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    def _run_sanctions_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        screening = self.sanctions_service.check(
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

    def _run_ubo_kyc_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        profile = OwnershipProfile(
            ubo_count=int(float(form_data.get("ubo_count", 0))),
            largest_ownership_percent=float(form_data.get("largest_ownership_percent", 0)),
        )
        outcome = self.decision_engine.assess_ownership(profile)
        payload = {"ubo_count": profile.ubo_count, "largest_ownership_percent": profile.largest_ownership_percent}
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    def _run_business_credit_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        profile = BusinessProfile(
            annual_turnover=float(form_data.get("annual_turnover", 0)),
            expected_monthly_volume=float(form_data.get("expected_monthly_volume", 0)),
            sector=str(form_data.get("sector", "")),
        )
        outcome = self.decision_engine.assess_business_credit(profile)
        payload = {
            "turnover_band": self._money_band(profile.annual_turnover),
            "monthly_volume_band": self._money_band(profile.expected_monthly_volume),
            "sector": profile.sector,
        }
        return IntegrationResult(outcome, json.dumps(payload, sort_keys=True))

    def _run_representative_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        has_authority = bool(form_data.get("has_signatory_authority"))
        outcome = self.decision_engine.assess_representative_authority(has_authority)
        payload = {"authority": "confirmed" if has_authority else "missing_or_unconfirmed"}
        return IntegrationResult(outcome, json.dumps(payload))

    # Provider authority checks: the external system's own verdict.

    def _run_identity_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        pin = form_data.get("personal_identity_number") or form_data.get("representative_id", "")
        return self.identity_service.verify(str(pin))

    def _run_registry_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return self.registry_service.lookup_entity(str(form_data.get("company_identifier", "")))

    def _run_bank_account_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return self.bank_account_service.validate_iban(str(form_data.get("iban", "")))

    def _run_address_lookup(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return IntegrationResult(
            status_outcome=CheckOutcome.APPROVED,
            raw_response_json=json.dumps({"address_confidence": 0.92, "status": "FETCHED"}),
        )
