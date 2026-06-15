from dataclasses import dataclass
from domain.states import ApplicationStatus, TERMINAL_APPLICATION_STATUSES

@dataclass
class ApplicationEntity:
    id: str
    country: str
    account_type: str
    status: ApplicationStatus
    version: int

    def transition_status(self, new_status: ApplicationStatus) -> None:
        if self.status in TERMINAL_APPLICATION_STATUSES:
            raise RuntimeError(f"Cannot transition from terminal state {self.status} to {new_status}")
        self.status = new_status
