import json
import hashlib
import hmac
from typing import Dict, Any, Optional
from config import settings
from domain.ports import (
    ApplicationRepository, 
    IdentityVerificationService, 
    SanctionsCheckService, 
    CreditBureauService
)
from domain.flow_registry import flow_registry
from domain.entities import ApplicationEntity
from domain.states import ApplicationStatus
from domain.decisioning import AutomatedDecisionEngine


class StateTransitionError(Exception):
    pass

class OnboardingService:
    def __init__(
        self,
        repository: ApplicationRepository,
        identity_service: IdentityVerificationService,
        sanctions_service: SanctionsCheckService,
        credit_service: CreditBureauService
    ):
        self.repository = repository
        self.identity_service = identity_service
        self.sanctions_service = sanctions_service
        self.credit_service = credit_service

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

        # Evaluate platform integrations
        for integration in step_config.required_integrations:
            if integration == "identity":
                pin = form_data.get("personal_identity_number") or form_data.get("representative_id", "")
                result = self.identity_service.verify(pin)
                self.repository.log_integration_check(
                    application_id, "identity", result.status_outcome, result.raw_response_json, request_id
                )
                
                if result.status_outcome in ["REJECTED", "MANUAL_REVIEW"]:
                    new_status = ApplicationStatus(result.status_outcome)
                    application.transition_status(new_status)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "address_lookup":
                # FIX: Gracefully process or log address checks instead of letting it drop through unhandled
                mock_json = json.dumps({"address_confidence": 0.92, "status": "FETCHED"})
                self.repository.log_integration_check(
                    application_id, "address_lookup", "APPROVED", mock_json, request_id
                )

            elif integration == "sanctions":
                is_pep = str(form_data.get("is_pep", "")).lower() == "true"
                tax_residency = form_data.get("tax_residency", "")
                
                decision_outcome = AutomatedDecisionEngine.evaluate_compliance_risk(tax_residency, is_pep)
                mock_json = json.dumps({
                    "screening_result": "possible_hit" if is_pep else "no_hit",
                    "restricted_tax_residency": decision_outcome == ApplicationStatus.REJECTED,
                    "outcome": decision_outcome.value,
                })
                self.repository.log_integration_check(
                    application_id, "sanctions", decision_outcome.value, mock_json, request_id
                )
                
                if decision_outcome in [ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
                    application.transition_status(decision_outcome)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "credit_bureau":
                try:
                    income = float(form_data.get("monthly_income", 0))
                    expenses = float(form_data.get("monthly_expenses", 0))
                    debts = float(form_data.get("outstanding_debts", 0))
                except (TypeError, ValueError) as err:
                    raise ValueError("Financial inputs must be numeric.") from err
                
                decision_outcome = AutomatedDecisionEngine.evaluate_financial_risk(income, expenses, debts)
                disposable_income = income - expenses
                debt_to_income_ratio = debts / income if income > 0 else 0
                mock_json = json.dumps({
                    "income_band": self._money_band(income),
                    "disposable_income_band": self._money_band(max(disposable_income, 0)),
                    "high_debt_to_income": debt_to_income_ratio > 0.60,
                    "outcome": decision_outcome.value,
                })
                self.repository.log_integration_check(
                    application_id, "credit_bureau", decision_outcome.value, mock_json, request_id
                )
                
                application.transition_status(decision_outcome)
                self.repository.update_application_status(application.id, application.status.value, application.version)
                return {"status": application.status.value, "next_step_id": None}

            elif integration == "registry":
                company_identifier = str(form_data.get("company_identifier", ""))
                if company_identifier.startswith("00"):
                    outcome = ApplicationStatus.REJECTED
                    payload = {"registry_status": "not_found"}
                elif company_identifier.endswith("1111"):
                    outcome = ApplicationStatus.MANUAL_REVIEW
                    payload = {"registry_status": "manual_review", "reason": "ambiguous_company_match"}
                else:
                    outcome = ApplicationStatus.APPROVED
                    payload = {"registry_status": "active_company"}
                self.repository.log_integration_check(application_id, "registry", outcome.value, json.dumps(payload), request_id)
                if outcome in [ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
                    application.transition_status(outcome)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "representative":
                has_authority = bool(form_data.get("has_signatory_authority"))
                outcome = ApplicationStatus.APPROVED if has_authority else ApplicationStatus.MANUAL_REVIEW
                payload = {"authority": "confirmed" if has_authority else "missing_or_unconfirmed"}
                self.repository.log_integration_check(application_id, "representative", outcome.value, json.dumps(payload), request_id)
                if outcome == ApplicationStatus.MANUAL_REVIEW:
                    application.transition_status(outcome)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "ubo_kyc":
                ubo_count = float(form_data.get("ubo_count", 0))
                largest_ownership = float(form_data.get("largest_ownership_percent", 0))
                if ubo_count <= 0:
                    outcome = ApplicationStatus.REJECTED
                    payload = {"ubo_status": "missing_ubo"}
                elif largest_ownership >= 75:
                    outcome = ApplicationStatus.MANUAL_REVIEW
                    payload = {"ubo_status": "concentrated_ownership"}
                else:
                    outcome = ApplicationStatus.APPROVED
                    payload = {"ubo_status": "verified"}
                self.repository.log_integration_check(application_id, "ubo_kyc", outcome.value, json.dumps(payload), request_id)
                if outcome in [ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
                    application.transition_status(outcome)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "business_credit":
                turnover = float(form_data.get("annual_turnover", 0))
                monthly_volume = float(form_data.get("expected_monthly_volume", 0))
                sector = str(form_data.get("sector", ""))
                if turnover <= 0:
                    outcome = ApplicationStatus.REJECTED
                    payload = {"business_credit": "no_turnover"}
                elif sector == "FINANCIAL_SERVICES" or monthly_volume > turnover:
                    outcome = ApplicationStatus.MANUAL_REVIEW
                    payload = {"business_credit": "enhanced_due_diligence"}
                else:
                    outcome = ApplicationStatus.APPROVED
                    payload = {"business_credit": "acceptable"}
                payload["turnover_band"] = self._money_band(turnover)
                payload["monthly_volume_band"] = self._money_band(monthly_volume)
                self.repository.log_integration_check(application_id, "business_credit", outcome.value, json.dumps(payload), request_id)
                if outcome in [ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
                    application.transition_status(outcome)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "bank_account":
                iban = str(form_data.get("iban", ""))
                outcome = ApplicationStatus.MANUAL_REVIEW if iban.endswith("9999") else ApplicationStatus.APPROVED
                payload = {"iban_status": "name_mismatch" if outcome == ApplicationStatus.MANUAL_REVIEW else "iban_verified"}
                self.repository.log_integration_check(application_id, "bank_account", outcome.value, json.dumps(payload), request_id)
                if outcome == ApplicationStatus.MANUAL_REVIEW:
                    application.transition_status(outcome)
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
