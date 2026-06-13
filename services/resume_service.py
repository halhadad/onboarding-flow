from typing import Dict, Any, Optional
from domain.ports import ApplicationRepository
from domain.flow_registry import FlowRegistry, flow_registry as default_flow_registry
from domain.states import ApplicationStatus, is_customer_submittable

class ResumeApplicationError(Exception):
    pass

class ResumeService:
    def __init__(self, repository: ApplicationRepository, registry: Optional[FlowRegistry] = None):
        self.repository = repository
        self.flow_registry = registry or default_flow_registry

    def resume_by_token(self, resume_token: str) -> Dict[str, Any]:
        context = self.repository.get_application_context_by_resume_token(resume_token)
        if not context:
            raise ResumeApplicationError("Resume token was not found.")
        if context.get("resume_token_expired"):
            raise ResumeApplicationError("Resume token has expired.")
        return self.resume_session(
            str(context["id"]),
            str(context["country"]),
            str(context["account_type"]),
        )

    def resume_session(self, application_id: str, country: str, account_type: str) -> Dict[str, Any]:
        """
        Calculates the operational state of an incomplete onboarding session.
        Determines the exact step to resume by scanning step-level answers.
        """
        current_status_str = self.repository.get_application_status(application_id)
        if not current_status_str:
            raise ResumeApplicationError(f"No active session found matching ID: {application_id}")

        status = ApplicationStatus(current_status_str)

        # Customers can only resume an application that is still open for input.
        # Terminal (APPROVED/REJECTED) and MANUAL_REVIEW states are not resumable.
        if not is_customer_submittable(status):
            raise ResumeApplicationError(
                f"Cannot resume session because the application is no longer open for input: {status.value}"
            )

        flow = self.flow_registry.get_flow(country, account_type)
        
        resume_step_id = flow.steps[0].step_id
        for step in flow.steps:
            existing_response = self.repository.get_step_response(application_id, step.step_id)
            if existing_response:
                next_step_id = flow.get_next_step_id(step.step_id)
                if next_step_id:
                    resume_step_id = next_step_id
            else:
                resume_step_id = step.step_id
                break

        return {
            "application_id": application_id,
            "country": country,
            "account_type": account_type,
            "next_step_id": resume_step_id,
            "status": status.value
        }
