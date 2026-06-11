import json
from domain.ports import IntegrationResult

class MockBankAccountService:
    def validate_account(self, routing_number: str, account_number: str) -> IntegrationResult:
        if routing_number.strip() == "9999":
            return IntegrationResult(status_outcome="REJECTED", raw_response_json=json.dumps({"error": "INVALID_BIC"}))
        return IntegrationResult(status_outcome="APPROVED", raw_response_json=json.dumps({"status": "VALIDATED"}))