import json
from domain.ports import IntegrationResult, RegistryLookupService
from domain.enums import RegistryStatus
from domain.states import CheckOutcome


_OUTCOME = {
    RegistryStatus.ACTIVE: CheckOutcome.APPROVED,
    RegistryStatus.NOT_FOUND: CheckOutcome.REJECTED,
    RegistryStatus.AMBIGUOUS: CheckOutcome.MANUAL_REVIEW,
}


class MockRegistryService(RegistryLookupService):

    async def lookup_entity(self, tax_id: str) -> IntegrationResult:
        if tax_id.startswith("00"):
            status = RegistryStatus.NOT_FOUND
        elif tax_id.endswith("1111"):
            status = RegistryStatus.AMBIGUOUS
        else:
            status = RegistryStatus.ACTIVE
        return IntegrationResult(_OUTCOME[status], json.dumps({"registry_status": status.value}))
