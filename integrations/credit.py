import json
from domain.ports import CreditBureauService, IntegrationResult
from domain.states import CheckOutcome

class MockCreditBureauService(CreditBureauService):

    def evaluate(self, monthly_income: float, monthly_expenses: float, outstanding_debts: float) -> IntegrationResult:
        disposable_income = monthly_income - monthly_expenses
        
        # Immediate rejection if the basic net household balance is underwater
        if disposable_income <= 0:
            payload = {"disposable_income": disposable_income, "debt_flags": ["NEGATIVE_SURPLUS"], "score": 310}
            return IntegrationResult(
                status_outcome=CheckOutcome.REJECTED,
                raw_response_json=json.dumps(payload)
            )

        # Calculate a basic debt-to-income metric
        debt_to_income_ratio = outstanding_debts / monthly_income if monthly_income > 0 else 0

        if debt_to_income_ratio > 0.60:
            payload = {"disposable_income": disposable_income, "debt_flags": ["HIGH_LEVERAGE_RISK"], "score": 480}
            return IntegrationResult(
                status_outcome=CheckOutcome.MANUAL_REVIEW,
                raw_response_json=json.dumps(payload)
            )

        payload = {"disposable_income": disposable_income, "debt_flags": [], "score": 780}
        return IntegrationResult(
            status_outcome=CheckOutcome.APPROVED,
            raw_response_json=json.dumps(payload)
        )
