from domain.states import ApplicationStatus

class AutomatedDecisionEngine:

    @staticmethod
    def evaluate_financial_risk(income: float, expenses: float, debts: float) -> ApplicationStatus:
        disposable_income = income - expenses
        
        if disposable_income <= 0:
            return ApplicationStatus.REJECTED
            
        debt_to_income_ratio = debts / income if income > 0 else 0
        if debt_to_income_ratio > 0.60:
            return ApplicationStatus.MANUAL_REVIEW
            
        return ApplicationStatus.APPROVED

    @staticmethod
    def evaluate_compliance_risk(tax_residency: str, is_pep: bool) -> ApplicationStatus:
        normalized_country = tax_residency.strip().upper()
        
        if normalized_country in ["IR", "KP", "SY"]:
            return ApplicationStatus.REJECTED
            
        if is_pep:
            return ApplicationStatus.MANUAL_REVIEW
            
        return ApplicationStatus.APPROVED