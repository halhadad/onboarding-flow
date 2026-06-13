from domain.ports import SanctionsCheckService
from domain.decisioning import SanctionsScreening
from domain.countries import SANCTIONED_RESIDENCIES


class MockSanctionsCheckService(SanctionsCheckService):
    """Deterministic sanctions screening mock; reports signals, does not decide."""

    def check(self, tax_residency: str, is_pep: bool) -> SanctionsScreening:
        clean_residency = tax_residency.strip().upper()
        sanctions_hit = clean_residency in SANCTIONED_RESIDENCIES
        return SanctionsScreening(
            sanctions_hit=sanctions_hit,
            pep_hit=bool(is_pep),
            matched_country=clean_residency if sanctions_hit else None,
        )
