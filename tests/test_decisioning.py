from domain.decisioning import AutomatedDecisionEngine
from domain.states import ApplicationStatus


def test_financial_risk_rejects_negative_disposable_income():
    assert AutomatedDecisionEngine.evaluate_financial_risk(1000, 1200, 0) == ApplicationStatus.REJECTED


def test_financial_risk_refers_high_debt_to_manual_review():
    assert AutomatedDecisionEngine.evaluate_financial_risk(1000, 200, 700) == ApplicationStatus.MANUAL_REVIEW


def test_compliance_risk_refers_pep_to_manual_review():
    assert AutomatedDecisionEngine.evaluate_compliance_risk("SE", True) == ApplicationStatus.MANUAL_REVIEW
