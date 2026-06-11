from dataclasses import dataclass, field
from typing import Dict, Any, List
from domain.states import ApplicationStatus

@dataclass
class ApplicationEntity:
    id: str
    country: str
    account_type: str
    status: ApplicationStatus
    version: int
    responses: Dict[str, Any] = field(default_factory=dict)

    def can_transition_to(self, new_status: ApplicationStatus) -> bool:
        """
        Enforces terminal state invariants. Once an application reaches 
        APPROVED, REJECTED, or MANUAL_REVIEW, no further changes are permitted.
        """
        if self.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED, ApplicationStatus.MANUAL_REVIEW]:
            return False
        return True

    def transition_status(self, new_status: ApplicationStatus) -> None:
        if not self.can_transition_to(new_status):
            raise RuntimeError(f"Cannot transition application from terminal state {self.status} to {new_status}")
        self.status = new_status