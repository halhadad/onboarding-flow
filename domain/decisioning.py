from dataclasses import dataclass, field
from typing import Optional, Tuple
from config import settings
from domain.enums import Sector
from domain.states import CheckOutcome


@dataclass(frozen=True)
class CreditAssessment:
    score: int
    disposable_income: float
    debt_to_income_ratio: float
    flags: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SanctionsScreening:
    sanctions_hit: bool
    pep_hit: bool
    matched_country: Optional[str] = None


@dataclass(frozen=True)
class OwnershipProfile:
    ubo_count: int
    largest_ownership_percent: float


@dataclass(frozen=True)
class BusinessProfile:
    annual_turnover: float
    expected_monthly_volume: float
    sector: str


class AutomatedDecisionEngine:

    def __init__(
        self,
        high_dti_threshold: float = settings.DTI_THRESHOLD,
        concentrated_ownership_threshold: float = settings.OWNERSHIP_CONCENTRATION_THRESHOLD,
        high_risk_sectors: frozenset[str] = frozenset({Sector.FINANCIAL_SERVICES.value}),
    ) -> None:
        self.high_dti_threshold = high_dti_threshold
        self.concentrated_ownership_threshold = concentrated_ownership_threshold
        self.high_risk_sectors = high_risk_sectors

    def assess_affordability(self, assessment: CreditAssessment) -> CheckOutcome:
        if assessment.disposable_income <= 0:
            return CheckOutcome.REJECTED
        if assessment.debt_to_income_ratio > self.high_dti_threshold:
            return CheckOutcome.MANUAL_REVIEW
        return CheckOutcome.APPROVED

    def assess_sanctions(self, screening: SanctionsScreening) -> CheckOutcome:
        if screening.sanctions_hit:
            return CheckOutcome.REJECTED
        if screening.pep_hit:
            return CheckOutcome.MANUAL_REVIEW
        return CheckOutcome.APPROVED

    def assess_ownership(self, profile: OwnershipProfile) -> CheckOutcome:
        if profile.ubo_count <= 0:
            return CheckOutcome.REJECTED
        if profile.largest_ownership_percent >= self.concentrated_ownership_threshold:
            return CheckOutcome.MANUAL_REVIEW
        return CheckOutcome.APPROVED

    def assess_business_credit(self, profile: BusinessProfile) -> CheckOutcome:
        if profile.annual_turnover <= 0:
            return CheckOutcome.REJECTED
        if profile.sector.lower() in self.high_risk_sectors or profile.expected_monthly_volume > profile.annual_turnover:
            return CheckOutcome.MANUAL_REVIEW
        return CheckOutcome.APPROVED

    def assess_representative_authority(self, has_authority: bool) -> CheckOutcome:
        return CheckOutcome.APPROVED if has_authority else CheckOutcome.MANUAL_REVIEW
