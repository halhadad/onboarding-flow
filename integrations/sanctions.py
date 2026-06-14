from typing import FrozenSet

from domain.ports import SanctionsCheckService
from domain.decisioning import SanctionsScreening

_DEFAULT_SANCTIONED_RESIDENCIES = frozenset({"IR", "KP", "SY"})


class MockSanctionsCheckService(SanctionsCheckService):
    """Deterministic sanctions screening mock; reports signals, does not decide."""

    def __init__(self, sanctioned_residencies: FrozenSet[str] = _DEFAULT_SANCTIONED_RESIDENCIES):
        self.sanctioned_residencies = sanctioned_residencies

    async def check(self, tax_residency: str, is_pep: bool) -> SanctionsScreening:
        clean_residency = tax_residency.strip().upper()
        sanctions_hit = clean_residency in self.sanctioned_residencies
        return SanctionsScreening(
            sanctions_hit=sanctions_hit,
            pep_hit=bool(is_pep),
            matched_country=clean_residency if sanctions_hit else None,
        )
