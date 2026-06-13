from dataclasses import dataclass, field
from typing import Dict, Any, List
from domain.states import ApplicationStatus, TERMINAL_APPLICATION_STATUSES

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
        Enforces the terminal-state invariant: once an application reaches a
        terminal status (APPROVED or REJECTED) it can never change again.
        MANUAL_REVIEW is intentionally NOT terminal — an operator can still move
        it on to APPROVED or REJECTED — so transitions out of it are allowed.
        """
        if self.status in TERMINAL_APPLICATION_STATUSES:
            return False
        return True

    def transition_status(self, new_status: ApplicationStatus) -> None:
        if not self.can_transition_to(new_status):
            raise RuntimeError(f"Cannot transition application from terminal state {self.status} to {new_status}")
        self.status = new_status
