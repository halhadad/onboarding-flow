import hashlib
import json
import logging
from typing import Any, Dict, Optional

from audit.log import SecurityAuditLogger
from domain.decisioning import AutomatedDecisionEngine
from domain.ports import (
    ApplicationRepository,
    IdentityVerificationService,
    SanctionsCheckService,
    CreditBureauService,
    RegistryLookupService,
    BankAccountValidationService,
)
from domain.enums import AuditField
from domain.flow_registry import FlowRegistry, flow_registry as default_flow_registry
from domain.entities import ApplicationEntity
from domain.exceptions import StateTransitionError
from domain.states import ApplicationStatus, CheckOutcome, is_customer_submittable
from services.integration_runner import IntegrationRunner
from shared.util import new_uuid

logger = logging.getLogger("onboarding.service")


class OnboardingService:
    """Orchestrates one step submission: guard state, run checks, advance."""

    def __init__(
        self,
        repository: ApplicationRepository,
        identity_service: IdentityVerificationService,
        sanctions_service: SanctionsCheckService,
        credit_service: CreditBureauService,
        registry_service: RegistryLookupService,
        bank_account_service: BankAccountValidationService,
        decision_engine: Optional[AutomatedDecisionEngine] = None,
        registry: Optional[FlowRegistry] = None,
        integration_timeout_seconds: float = 2.0,
        integration_max_attempts: int = 2,
        integration_demo_delay_seconds: float = 0.0,
    ):
        self.repository = repository
        self.flow_registry = registry or default_flow_registry
        self.decision_engine = decision_engine or AutomatedDecisionEngine()
        self.integration_runner = IntegrationRunner(
            identity_service=identity_service,
            sanctions_service=sanctions_service,
            credit_service=credit_service,
            registry_service=registry_service,
            bank_account_service=bank_account_service,
            decision_engine=self.decision_engine,
            timeout_seconds=integration_timeout_seconds,
            max_attempts=integration_max_attempts,
            demo_delay_seconds=integration_demo_delay_seconds,
        )

    def start_application(self, country: str, account_type: str, request_id: str) -> tuple[str, str]:
        """Create an application in one transaction; return (id, resume token)."""
        application_id = new_uuid()
        with self.repository.atomic():
            token = self.repository.create_application(application_id, country, account_type, request_id)
        return application_id, token

    def _payload_fingerprint(self, form_data: Dict[str, Any]) -> str:
        """Content fingerprint to detect an unchanged resubmission."""
        normalised = json.dumps(form_data, sort_keys=True)
        return hashlib.sha256(normalised.encode()).hexdigest()

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

    async def process_step_submission(
        self,
        application_id: str,
        country: str,
        account_type: str,
        step_id: str,
        form_data: Dict[str, Any],
        current_version: int,
        request_id: str
    ) -> Dict[str, Any]:
        """Validate, run the step's checks, and advance the application."""
        flow = self.flow_registry.get_flow(country, account_type)
        step_config = flow.get_step_by_id(step_id)
        if not step_config:
            raise ValueError(f"Step {step_id} does not map to this specific application configuration workflow.")

        logger.info(
            "step_submission_started",
            extra={
                AuditField.REQUEST_ID.value: request_id,
                AuditField.APPLICATION_ID.value: application_id,
                AuditField.STEP_ID.value: step_id,
                AuditField.COUNTRY.value: country,
                AuditField.ACCOUNT_TYPE.value: account_type,
            },
        )

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

        # Gate shared with the web layer; covers terminal and MANUAL_REVIEW states.
        if not is_customer_submittable(application.status):
            raise StateTransitionError(
                f"This application can no longer be modified by the applicant (status: {application.status.value})."
            )

        self._assert_step_is_reachable(application_id, flow, step_id)

        existing_response = self.repository.get_step_response(application_id, step_id)
        current_hash = self._payload_fingerprint(form_data)

        if existing_response and existing_response.get("payload_hash") == current_hash:
            next_step_id = flow.get_next_step_id(step_id)
            return {"status": application.status.value, "next_step_id": next_step_id, "reasons": []}

        # Run all checks (async, with timeout/retry) before persisting; a reviewer
        # needs every reason. A transient failure raises here, before any write,
        # so the step is not finalised and a retry runs it again.
        results = []
        for integration in step_config.required_integrations:
            result = await self.integration_runner.run(integration, application_id, form_data, request_id)
            results.append((integration, result))

        # Collect every adverse reason and decide the resulting status.
        reasons = [
            f"{getattr(integration, 'value', integration)}:{result.status_outcome.value}"
            for integration, result in results
            if result.status_outcome != CheckOutcome.APPROVED
        ]
        rejected = any(r.status_outcome == CheckOutcome.REJECTED for _, r in results)
        needs_review = any(r.status_outcome == CheckOutcome.MANUAL_REVIEW for _, r in results)
        next_step_id = flow.get_next_step_id(step_id)

        if rejected:
            final_status = ApplicationStatus.REJECTED
        elif needs_review:
            final_status = ApplicationStatus.MANUAL_REVIEW
        elif next_step_id is None:
            final_status = ApplicationStatus.APPROVED
        else:
            final_status = ApplicationStatus.IN_PROGRESS

        is_final = final_status is not ApplicationStatus.IN_PROGRESS
        decision_reasons = reasons if (rejected or needs_review) else []
        application.transition_status(final_status)

        # One transaction for every write: a concurrency conflict or duplicate step
        # rolls back the whole submission, so the database never holds partial state.
        with self.repository.atomic():
            self.repository.save_step_response(application_id, step_id, form_data, current_hash)
            for integration, result in results:
                self.repository.log_integration_check(
                    application_id, integration, result.status_outcome, result.raw_response_json, request_id
                )
            self.repository.update_application_status(application.id, final_status.value, application.version)
            if is_final:
                self.repository.save_decision(application.id, final_status.value, decision_reasons)

        SecurityAuditLogger.log_state_mutation(
            application.id, "application_status", final_status.value, request_id
        )
        logger.info(
            "step_submission_completed",
            extra={
                AuditField.REQUEST_ID.value: request_id,
                AuditField.APPLICATION_ID.value: application_id,
                AuditField.STEP_ID.value: step_id,
                AuditField.OUTCOME.value: final_status.value,
            },
        )
        return {
            "status": final_status.value,
            "next_step_id": None if is_final else next_step_id,
            "reasons": decision_reasons,
        }
