import json
from domain.ports import IntegrationResult

class MockRegistryService:
    def lookup_entity(self, tax_id: str) -> IntegrationResult:
        if tax_id.startswith("00"):
            return IntegrationResult(status_outcome="REJECTED", raw_response_json=json.dumps({"registry": "NOT_FOUND"}))
        return IntegrationResult(status_outcome="APPROVED", raw_response_json=json.dumps({"registry": "MATCHED"}))