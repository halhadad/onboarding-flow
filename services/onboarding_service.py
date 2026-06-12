import json
import hashlib
import hmac
from typing import Callable, Dict, Any
from config import settings
from domain.ports import (
    ApplicationRepository, 
    IdentityVerificationService, 
    SanctionsCheckService, 
    CreditBureauService,
    RegistryLookupService,
    BankAccountValidationService,
    IntegrationResult,
)
from domain.flow_registry import flow_registry
from domain.entities import ApplicationEntity
from domain.states import ApplicationStatus


class StateTransitionError(Exception):
    pass

class OnboardingService:
    def __init__(
        self,
        repository: ApplicationRepository,
        identity_service: IdentityVerificationService,
        sanctions_service: SanctionsCheckService,
        credit_service: CreditBureauService,
        registry_service: RegistryLookupService,
        bank_account_service: BankAccountValidationService
    ):
        self.repository = repository
        self.identity_service = identity_service
        self.sanctions_service = sanctions_service
        self.credit_service = credit_service
        self.registry_service = registry_service
        self.bank_account_service = bank_account_service
        self.integration_handlers: Dict[str, Callable[[str, Dict[str, Any], str], IntegrationResult]] = {
            "identity": self._run_identity_check,
            "address_lookup": self._run_address_lookup,
            "sanctions": self._run_sanctions_check,
            "credit_bureau": self._run_credit_bureau_check,
            "registry": self._run_registry_check,
            "representative": self._run_representative_check,
            "ubo_kyc": self._run_ubo_kyc_check,
            "business_credit": self._run_business_credit_check,
            "bank_account": self._run_bank_account_check,
        }

    def _generate_payload_hash(self, form_data: Dict[str, Any]) -> str:
        """Generates a keyed digest so low-entropy identifiers are not exposed to offline guessing."""
        serialized = json.dumps(form_data, sort_keys=True)
        return hmac.new(
            settings.ONBOARDING_INTERNAL_SECRET.encode("utf-8"),
            serialized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _money_band(self, value: float) -> str:
        if value < 1000:
            return "below_1000"
        if value < 3000:
            return "1000_2999"
        if value < 10000:
            return "3000_9999"
        return "10000_plus"

    def _assert_step_is_reachable(self, application_id: str, flow, step_id: str) -> None:
        requested_index = next(
            (index for index, step in enumerate(flow.steps) if step.step_id == step_id),
            None,
        )
        if requested_index is None:
            raise StateTransitionError("Requested step is not part of this onboarding flow.")

        for previous_step in flow.steps[:requested_index]:
            if not self.repository.get_step_response(application_id, previous_step.step_id):
                raise StateTransitionError(
                    f"Step '{step_id}' cannot be submitted before completing '{previous_step.step_id}'."
                )

    def _run_identity_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        pin = form_data.get("personal_identity_number") or form_data.get("representative_id", "")
        return self.identity_service.verify(str(pin))

    def _run_address_lookup(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return IntegrationResult(
            status_outcome="APPROVED",
            raw_response_json=json.dumps({"address_confidence": 0.92, "status": "FETCHED"}),
        )

    def _run_sanctions_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        is_pep = bool(form_data.get("is_pep"))
        tax_residency = str(form_data.get("tax_residency", ""))
        return self.sanctions_service.check(tax_residency, is_pep)

    def _run_credit_bureau_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        try:
            income = float(form_data.get("monthly_income", 0))
            expenses = float(form_data.get("monthly_expenses", 0))
            debts = float(form_data.get("outstanding_debts", 0))
        except (TypeError, ValueError) as err:
            raise ValueError("Financial inputs must be numeric.") from err
        return self.credit_service.evaluate(income, expenses, debts)

    def _run_registry_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return self.registry_service.lookup_entity(str(form_data.get("company_identifier", "")))

    def _run_representative_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        has_authority = bool(form_data.get("has_signatory_authority"))
        payload = {"authority": "confirmed" if has_authority else "missing_or_unconfirmed"}
        return IntegrationResult(
            status_outcome="APPROVED" if has_authority else "MANUAL_REVIEW",
            raw_response_json=json.dumps(payload),
        )

    def _run_ubo_kyc_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        ubo_count = float(form_data.get("ubo_count", 0))
        largest_ownership = float(form_data.get("largest_ownership_percent", 0))
        if ubo_count <= 0:
            return IntegrationResult("REJECTED", json.dumps({"ubo_status": "missing_ubo"}))
        if largest_ownership >= 75:
            return IntegrationResult("MANUAL_REVIEW", json.dumps({"ubo_status": "concentrated_ownership"}))
        return IntegrationResult("APPROVED", json.dumps({"ubo_status": "verified"}))

    def _run_business_credit_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        turnover = float(form_data.get("annual_turnover", 0))
        monthly_volume = float(form_data.get("expected_monthly_volume", 0))
        sector = str(form_data.get("sector", "")).lower()
        if turnover <= 0:
            outcome = ApplicationStatus.REJECTED
            payload = {"business_credit": "no_turnover"}
        elif sector == "financial_services" or monthly_volume > turnover:
            outcome = ApplicationStatus.MANUAL_REVIEW
            payload = {"business_credit": "enhanced_due_diligence"}
        else:
            outcome = ApplicationStatus.APPROVED
            payload = {"business_credit": "acceptable"}
        payload["turnover_band"] = self._money_band(turnover)
        payload["monthly_volume_band"] = self._money_band(monthly_volume)
        return IntegrationResult(outcome.value, json.dumps(payload))

    def _run_bank_account_check(self, application_id: str, form_data: Dict[str, Any], request_id: str) -> IntegrationResult:
        return self.bank_account_service.validate_iban(str(form_data.get("iban", "")))

    def process_step_submission(
        self,
        application_id: str,
        country: str,
        account_type: str,
        step_id: str,
        form_data: Dict[str, Any],
        current_version: int,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Orchestrates step progression logic using pure domain models. Reconstructs the application entity,
        evaluates risk matrices via the automated decision engine, and tracks concurrency protection.
        """
        flow = flow_registry.get_flow(country, account_type)
        step_config = flow.get_step_by_id(step_id)
        if not step_config:
            raise ValueError(f"Step {step_id} does not map to this specific application configuration workflow.")

        # Reconstruct the application model state cleanly from historical records
        current_status_str = self.repository.get_application_status(application_id)
        if current_status_str is None:
            raise ValueError(f"Application {application_id} does not exist.")
        application = ApplicationEntity(
            id=application_id,
            country=country,
            account_type=account_type,
            status=ApplicationStatus(current_status_str),
            version=current_version
        )

        if application.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
            raise StateTransitionError("Terminal applications cannot be changed.")

        self._assert_step_is_reachable(application_id, flow, step_id)

        existing_response = self.repository.get_step_response(application_id, step_id)
        current_hash = self._generate_payload_hash(form_data)
        
        if existing_response and existing_response.get("payload_hash") == current_hash:
            next_step_id = flow.get_next_step_id(step_id)
            return {"status": application.status.value, "next_step_id": next_step_id}

        # Persist the validated step payload before external checks so resumability and support state stay coherent.
        self.repository.save_step_response(application_id, step_id, form_data, current_hash)

        # Evaluate platform integrations through explicit handlers so flow config stays declarative.
        for integration in step_config.required_integrations:
            handler = self.integration_handlers.get(integration)
            if handler is None:
                raise ValueError(f"No integration handler registered for '{integration}'.")

            result = handler(application_id, form_data, request_id)
            self.repository.log_integration_check(
                application_id, integration, result.status_outcome, result.raw_response_json, request_id
            )

            if result.status_outcome in ["REJECTED", "MANUAL_REVIEW"]:
                application.transition_status(ApplicationStatus(result.status_outcome))
                self.repository.update_application_status(application.id, application.status.value, application.version)
                return {"status": application.status.value, "next_step_id": None}

        # Calculate step routing transition parameters
        next_step_id = flow.get_next_step_id(step_id)
        if next_step_id is None:
            application.transition_status(ApplicationStatus.APPROVED)
        else:
            application.transition_status(ApplicationStatus.IN_PROGRESS)

        # FIX: Enforce systemic transaction level state version increments on EVERY step execution boundary pass
        self.repository.update_application_status(application.id, application.status.value, application.version)
        return {"status": application.status.value, "next_step_id": next_step_id}
