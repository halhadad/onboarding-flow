import json
from domain.ports import BankAccountValidationService, IntegrationResult
from domain.states import CheckOutcome

class MockBankAccountService(BankAccountValidationService):
    def validate_iban(self, iban: str) -> IntegrationResult:
        clean_iban = iban.replace(" ", "").upper()
        if clean_iban.endswith("9999"):
            return IntegrationResult(
                status_outcome=CheckOutcome.MANUAL_REVIEW,
                raw_response_json=json.dumps({"iban_status": "name_mismatch"}),
            )
        return IntegrationResult(
            status_outcome=CheckOutcome.APPROVED,
            raw_response_json=json.dumps({"iban_status": "iban_verified"}),
        )
