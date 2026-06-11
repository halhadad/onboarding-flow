from typing import Dict, Any
from domain.ports import ApplicationRepository
from domain.flow_registry import flow_registry
from domain.states import ApplicationStatus

class ResumeApplicationError(Exception):
    pass

class ResumeService:
    def __init__(self, repository: ApplicationRepository):
        self.repository = repository

    def resume_session(self, application_id: str, country: str, account_type: str) -> Dict[str, Any]:
        """
        Calculates the operational state of an incomplete onboarding session.
        Determines the exact step to resume by scanning step-level answers.
        """
        current_status_str = self.repository.get_application_status(application_id)
        if not current_status_str:
            raise ResumeApplicationError(f"No active session found matching ID: {application_id}")

        status = ApplicationStatus(current_status_str)

        # Enforce state rules: Terminal statuses cannot mutate or resume
        if status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
            raise ResumeApplicationError(
                f"Cannot resume session because application has reached a terminal state: {status.value}"
            )

        flow = flow_registry.get_flow(country, account_type)
        
        resume_step_id = flow.steps[0].step_id
        completed_steps_count = 0

        for step in flow.steps:
            existing_response = self.repository.get_step_response(application_id, step.step_id)
            if existing_response:
                completed_steps_count += 1
                next_step_id = flow.get_next_step_id(step.step_id)
                if next_step_id:
                    resume_step_id = next_step_id
            else:
                resume_step_id = step.step_id
                break

        return {
            "application_id": application_id,
            "next_step_id": resume_step_id,
            "current_version": completed_steps_count + 1,
            "status": status.value
        }