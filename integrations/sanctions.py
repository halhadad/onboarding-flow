import json
from domain.ports import SanctionsCheckService, IntegrationResult
from domain.states import CheckOutcome

class MockSanctionsCheckService(SanctionsCheckService):

    def check(self, tax_residency: str, is_pep: bool) -> IntegrationResult:
        clean_residency = tax_residency.strip().upper()

        if clean_residency in ["IR", "KP", "SY"]:
            payload = {"blacklist_match": True, "country_code": clean_residency, "restriction_type": "FATF_PROHIBITED"}
            return IntegrationResult(
                status_outcome=CheckOutcome.REJECTED,
                raw_response_json=json.dumps(payload)
            )

        if is_pep:
            payload = {"watchlist_match": "possible_hit", "entity_type": "PEP_DOMESTIC", "requires_clerical_signoff": True}
            return IntegrationResult(
                status_outcome=CheckOutcome.MANUAL_REVIEW,
                raw_response_json=json.dumps(payload)
            )

        payload = {"watchlist_match": "no_hit", "aml_clearance": True}
        return IntegrationResult(
            status_outcome=CheckOutcome.APPROVED,
            raw_response_json=json.dumps(payload)
        )
