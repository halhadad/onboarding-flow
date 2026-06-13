from enum import Enum

class ApplicationStatus(str, Enum):
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECTED = "REJECTED"


class CheckOutcome(str, Enum):
    APPROVED = "APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECTED = "REJECTED"


TERMINAL_APPLICATION_STATUSES = frozenset(
    {
        ApplicationStatus.APPROVED,
        ApplicationStatus.MANUAL_REVIEW,
        ApplicationStatus.REJECTED,
    }
)
