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


# Final decision; can never change again.
TERMINAL_APPLICATION_STATUSES = frozenset(
    {
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
    }
)

# States where the customer may submit or resume a step.
# MANUAL_REVIEW is excluded: parked with a reviewer, not terminal.
CUSTOMER_SUBMITTABLE_STATUSES = frozenset(
    {
        ApplicationStatus.STARTED,
        ApplicationStatus.IN_PROGRESS,
    }
)


def is_customer_submittable(status: ApplicationStatus) -> bool:
    return status in CUSTOMER_SUBMITTABLE_STATUSES
