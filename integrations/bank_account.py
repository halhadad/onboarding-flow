import asyncio
import json
from domain.ports import BankAccountValidationService, IntegrationResult
from domain.enums import BankAccountStatus
from domain.states import CheckOutcome

# Provider authority check: the bank account result IS the verdict.
_OUTCOME = {
    BankAccountStatus.VERIFIED: CheckOutcome.APPROVED,
    BankAccountStatus.NAME_MISMATCH: CheckOutcome.MANUAL_REVIEW,
}

# An IBAN ending in this value hangs so the runner timeout
_UNREACHABLE_SENTINEL = "0000"
_HANG_SECONDS = 30.0


class MockBankAccountService(BankAccountValidationService):

    async def validate_iban(self, iban: str) -> IntegrationResult:
        clean_iban = iban.replace(" ", "").upper()
        if clean_iban.endswith(_UNREACHABLE_SENTINEL):
            await asyncio.sleep(_HANG_SECONDS)
        status = BankAccountStatus.NAME_MISMATCH if clean_iban.endswith("9999") else BankAccountStatus.VERIFIED
        return IntegrationResult(_OUTCOME[status], json.dumps({"iban_status": status.value}))
