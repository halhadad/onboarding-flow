from domain.ports import CreditBureauService
from domain.decisioning import CreditAssessment


class MockCreditBureauService(CreditBureauService):
    """Deterministic credit bureau mock; reports signals, does not decide."""

    def evaluate(self, monthly_income: float, monthly_expenses: float, outstanding_debts: float) -> CreditAssessment:
        disposable_income = monthly_income - monthly_expenses
        debt_to_income_ratio = outstanding_debts / monthly_income if monthly_income > 0 else 0.0

        if disposable_income <= 0:
            score, flags = 310, ("NEGATIVE_SURPLUS",)
        elif debt_to_income_ratio > 0.60:
            score, flags = 480, ("HIGH_LEVERAGE_RISK",)
        else:
            score, flags = 780, ()

        return CreditAssessment(
            score=score,
            disposable_income=disposable_income,
            debt_to_income_ratio=round(debt_to_income_ratio, 4),
            flags=flags,
        )
