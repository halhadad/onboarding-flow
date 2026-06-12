import json
from domain.ports import IntegrationResult, RegistryLookupService

class MockRegistryService(RegistryLookupService):
    def lookup_entity(self, tax_id: str) -> IntegrationResult:
        if tax_id.startswith("00"):
            return IntegrationResult(status_outcome="REJECTED", raw_response_json=json.dumps({"registry_status": "not_found"}))
        if tax_id.endswith("1111"):
            return IntegrationResult(
                status_outcome="MANUAL_REVIEW",
                raw_response_json=json.dumps({"registry_status": "manual_review", "reason": "ambiguous_company_match"}),
            )
        return IntegrationResult(status_outcome="APPROVED", raw_response_json=json.dumps({"registry_status": "active_company"}))
