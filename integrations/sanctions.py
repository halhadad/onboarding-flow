from domain.ports import SanctionsCheckService
from domain.decisioning import SanctionsScreening
from domain.countries import SANCTIONED_RESIDENCIES


class MockSanctionsCheckService(SanctionsCheckService):
    """Deterministic stand-in for a sanctions / PEP screening provider.

    Reports the raw screening signals only; the decision engine maps a hit to
    a rejection and a PEP match to manual review.
    """

    def check(self, tax_residency: str, is_pep: bool) -> SanctionsScreening:
        clean_residency = tax_residency.strip().upper()
        sanctions_hit = clean_residency in SANCTIONED_RESIDENCIES
        return SanctionsScreening(
            sanctions_hit=sanctions_hit,
            pep_hit=bool(is_pep),
            matched_country=clean_residency if sanctions_hit else None,
        )
