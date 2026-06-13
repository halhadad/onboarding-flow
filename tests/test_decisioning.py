from domain.decisioning import (
    AutomatedDecisionEngine,
    BusinessProfile,
    CreditAssessment,
    OwnershipProfile,
    SanctionsScreening,
)
from domain.states import CheckOutcome


def test_affordability_rejects_negative_disposable_income():
    engine = AutomatedDecisionEngine()
    report = CreditAssessment(score=310, disposable_income=-200.0, debt_to_income_ratio=0.0, flags=("NEGATIVE_SURPLUS",))
    assert engine.assess_affordability(report) == CheckOutcome.REJECTED


def test_affordability_refers_high_leverage_to_manual_review():
    engine = AutomatedDecisionEngine()
    report = CreditAssessment(score=480, disposable_income=800.0, debt_to_income_ratio=0.70, flags=("HIGH_LEVERAGE_RISK",))
    assert engine.assess_affordability(report) == CheckOutcome.MANUAL_REVIEW


def test_affordability_approves_healthy_profile():
    engine = AutomatedDecisionEngine()
    report = CreditAssessment(score=780, disposable_income=2000.0, debt_to_income_ratio=0.1)
    assert engine.assess_affordability(report) == CheckOutcome.APPROVED


def test_sanctions_hit_is_rejected():
    engine = AutomatedDecisionEngine()
    screening = SanctionsScreening(sanctions_hit=True, pep_hit=False, matched_country="IR")
    assert engine.assess_sanctions(screening) == CheckOutcome.REJECTED


def test_pep_match_is_referred_to_manual_review():
    engine = AutomatedDecisionEngine()
    screening = SanctionsScreening(sanctions_hit=False, pep_hit=True)
    assert engine.assess_sanctions(screening) == CheckOutcome.MANUAL_REVIEW


def test_clean_screening_is_approved():
    engine = AutomatedDecisionEngine()
    screening = SanctionsScreening(sanctions_hit=False, pep_hit=False)
    assert engine.assess_sanctions(screening) == CheckOutcome.APPROVED


def test_ownership_missing_ubo_is_rejected():
    engine = AutomatedDecisionEngine()
    assert engine.assess_ownership(OwnershipProfile(ubo_count=0, largest_ownership_percent=0)) == CheckOutcome.REJECTED


def test_ownership_concentrated_is_referred():
    engine = AutomatedDecisionEngine()
    assert engine.assess_ownership(OwnershipProfile(ubo_count=2, largest_ownership_percent=80)) == CheckOutcome.MANUAL_REVIEW


def test_business_credit_high_risk_sector_is_referred():
    engine = AutomatedDecisionEngine()
    profile = BusinessProfile(annual_turnover=100000, expected_monthly_volume=2000, sector="financial_services")
    assert engine.assess_business_credit(profile) == CheckOutcome.MANUAL_REVIEW


def test_business_credit_no_turnover_is_rejected():
    engine = AutomatedDecisionEngine()
    profile = BusinessProfile(annual_turnover=0, expected_monthly_volume=0, sector="retail")
    assert engine.assess_business_credit(profile) == CheckOutcome.REJECTED


def test_representative_without_authority_is_referred():
    engine = AutomatedDecisionEngine()
    assert engine.assess_representative_authority(False) == CheckOutcome.MANUAL_REVIEW
    assert engine.assess_representative_authority(True) == CheckOutcome.APPROVED
