import json
from domain.ports import IdentityVerificationService, IntegrationResult
from domain.enums import IdentityStatus
from domain.states import CheckOutcome

# Provider authority check: the provider's status IS the verdict, so the mapping
# to a CheckOutcome lives here, not in the decision engine. See ARCHITECTURE.md.
_OUTCOME = {
    IdentityStatus.VERIFIED: CheckOutcome.APPROVED,
    IdentityStatus.EXPIRED_ID: CheckOutcome.REJECTED,
    IdentityStatus.AMBIGUOUS: CheckOutcome.MANUAL_REVIEW,
}


class MockIdentityVerificationService(IdentityVerificationService):
    """Deterministic identity provider mock."""

    async def verify(self, personal_identity_number: str) -> IntegrationResult:
        clean_pin = personal_identity_number.strip()
        # The last four digits act as sentinels, so normal dates are not rejected.
        if clean_pin.endswith("0000"):
            status = IdentityStatus.EXPIRED_ID
        elif clean_pin.endswith("1111"):
            status = IdentityStatus.AMBIGUOUS
        else:
            status = IdentityStatus.VERIFIED
        return IntegrationResult(_OUTCOME[status], json.dumps({"verification_status": status.value}))
