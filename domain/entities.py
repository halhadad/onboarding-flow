from dataclasses import dataclass
from domain.states import ApplicationStatus, TERMINAL_APPLICATION_STATUSES

@dataclass
class ApplicationEntity:
    id: str
    country: str
    account_type: str
    status: ApplicationStatus
    version: int

    def can_transition_to(self, new_status: ApplicationStatus) -> bool:
        """False once the status is terminal; MANUAL_REVIEW is not terminal."""
        if self.status in TERMINAL_APPLICATION_STATUSES:
            return False
        return True

    def transition_status(self, new_status: ApplicationStatus) -> None:
        if not self.can_transition_to(new_status):
            raise RuntimeError(f"Cannot transition application from terminal state {self.status} to {new_status}")
        self.status = new_status
