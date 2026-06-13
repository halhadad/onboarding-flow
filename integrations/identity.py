import json
from domain.ports import IdentityVerificationService, IntegrationResult
from domain.states import CheckOutcome

class MockIdentityVerificationService(IdentityVerificationService):

    def verify(self, personal_identity_number: str) -> IntegrationResult:
        clean_pin = personal_identity_number.strip()

        # The last four digits act as sentinels, so normal dates are not rejected.
        if clean_pin.endswith("0000"):
            payload = {"error": "Document reference not found in national registry", "code": "EXPIRED_ID"}
            return IntegrationResult(
                status_outcome=CheckOutcome.REJECTED,
                raw_response_json=json.dumps(payload)
            )
        
        if clean_pin.endswith("1111"):
            payload = {"verification_status": "ambiguous_match", "confidence_score": 0.62}
            return IntegrationResult(
                status_outcome=CheckOutcome.MANUAL_REVIEW,
                raw_response_json=json.dumps(payload)
            )

        payload = {"verification_status": "verified", "confidence_score": 0.99, "registry_match": True}
        return IntegrationResult(
            status_outcome=CheckOutcome.APPROVED,
            raw_response_json=json.dumps(payload)
        )
