import json
from domain.ports import IdentityVerificationService, IntegrationResult

class MockIdentityVerificationService(IdentityVerificationService):

    def verify(self, personal_identity_number: str) -> IntegrationResult:
        clean_pin = personal_identity_number.strip()

        # Deterministic simulation rules based on input patterns
        if "0000" in clean_pin:
            payload = {"error": "Document reference not found in national registry", "code": "EXPIRED_ID"}
            return IntegrationResult(
                status_outcome="REJECTED",
                raw_response_json=json.dumps(payload)
            )
        
        if "1111" in clean_pin:
            payload = {"verification_status": "ambiguous_match", "confidence_score": 0.62}
            return IntegrationResult(
                status_outcome="MANUAL_REVIEW",
                raw_response_json=json.dumps(payload)
            )

        payload = {"verification_status": "verified", "confidence_score": 0.99, "registry_match": True}
        return IntegrationResult(
            status_outcome="APPROVED",
            raw_response_json=json.dumps(payload)
        )