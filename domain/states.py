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


# Terminal: the application has a final decision and can never change again.
TERMINAL_APPLICATION_STATUSES = frozenset(
    {
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
    }
)

# The only states in which a customer is allowed to submit/resume steps.
# MANUAL_REVIEW is deliberately excluded: the file is parked with a human
# reviewer, so the customer must not keep mutating it, but it is NOT terminal
# either — an operator can still move it to APPROVED or REJECTED.
CUSTOMER_SUBMITTABLE_STATUSES = frozenset(
    {
        ApplicationStatus.STARTED,
        ApplicationStatus.IN_PROGRESS,
    }
)


def is_terminal(status: ApplicationStatus) -> bool:
    return status in TERMINAL_APPLICATION_STATUSES


def is_customer_submittable(status: ApplicationStatus) -> bool:
    """True only when the applicant may submit or resume a step.

    This is the single gate used by both the web layer (routing) and the
    service layer (submission) so the two can never drift apart.
    """
    return status in CUSTOMER_SUBMITTABLE_STATUSES
