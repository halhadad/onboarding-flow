import json
import hashlib
from typing import Dict, Any, Optional
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
        """Generates a reproducible hash of form responses to check if input values changed."""
        serialized = json.dumps(form_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

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
        current_status_str = self.repository.get_application_status(application_id) or "STARTED"
        application = ApplicationEntity(
            id=application_id,
            country=country,
            account_type=account_type,
            status=ApplicationStatus(current_status_str),
            version=current_version
        )

        existing_response = self.repository.get_step_response(application_id, step_id)
        current_hash = self._generate_payload_hash(form_data)
        
        if existing_response and existing_response.get("payload_hash") == current_hash:
            next_step_id = flow.get_next_step_id(step_id)
            return {"status": application.status.value, "next_step_id": next_step_id}

        # Evaluate platform integrations
        for integration in step_config.required_integrations:
            if integration == "identity":
                pin = form_data.get("personal_identity_number", "")
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
                mock_json = json.dumps({"address": form_data.get("address"), "status": "FETCHED"})
                self.repository.log_integration_check(
                    application_id, "address_lookup", "APPROVED", mock_json, request_id
                )

            elif integration == "sanctions":
                is_pep = str(form_data.get("is_pep", "")).lower() == "true"
                tax_residency = form_data.get("tax_residency", "")
                
                decision_outcome = AutomatedDecisionEngine.evaluate_compliance_risk(tax_residency, is_pep)
                mock_json = json.dumps({"tax_residency": tax_residency, "is_pep": is_pep, "outcome": decision_outcome.value})
                self.repository.log_integration_check(
                    application_id, "sanctions", decision_outcome.value, mock_json, request_id
                )
                
                if decision_outcome in [ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
                    application.transition_status(decision_outcome)
                    self.repository.update_application_status(application.id, application.status.value, application.version)
                    return {"status": application.status.value, "next_step_id": None}

            elif integration == "credit_bureau":
                income = float(form_data.get("monthly_income", 0))
                expenses = float(form_data.get("monthly_expenses", 0))
                debts = float(form_data.get("outstanding_debts", 0))
                
                decision_outcome = AutomatedDecisionEngine.evaluate_financial_risk(income, expenses, debts)
                mock_json = json.dumps({"income": income, "expenses": expenses, "debts": debts, "outcome": decision_outcome.value})
                self.repository.log_integration_check(
                    application_id, "credit_bureau", decision_outcome.value, mock_json, request_id
                )
                
                application.transition_status(decision_outcome)
                self.repository.update_application_status(application.id, application.status.value, application.version)
                return {"status": application.status.value, "next_step_id": None}

        # Commit payload response
        self.repository.save_step_response(application_id, step_id, form_data, current_hash)
        
        # Calculate step routing transition parameters
        next_step_id = flow.get_next_step_id(step_id)
        if next_step_id is None:
            application.transition_status(ApplicationStatus.APPROVED)
        else:
            application.transition_status(ApplicationStatus.IN_PROGRESS)

        # FIX: Enforce systemic transaction level state version increments on EVERY step execution boundary pass
        self.repository.update_application_status(application.id, application.status.value, application.version)
        return {"status": application.status.value, "next_step_id": next_step_id}