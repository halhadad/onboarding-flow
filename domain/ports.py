from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Optional, Dict, Any
from dataclasses import dataclass
from domain.states import CheckOutcome
from domain.decisioning import CreditAssessment, SanctionsScreening

@dataclass(frozen=True)
class IntegrationResult:
    status_outcome: CheckOutcome
    raw_response_json: str

class ApplicationRepository(ABC):

    @abstractmethod
    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> str:
        pass

    @abstractmethod
    def get_application_status(self, application_id: str) -> Optional[str]:
        pass

    @abstractmethod
    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        pass

    @abstractmethod
    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        pass

    @abstractmethod
    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def log_integration_check(self, application_id: str, service_name: str, status_outcome: CheckOutcome, response_json: str, request_id: str) -> None:
        pass

    @abstractmethod
    def save_decision(self, application_id: str, outcome: str, reasons: list) -> None:
        pass

    @abstractmethod
    def atomic(self) -> AbstractContextManager[None]:
        pass


class IdentityVerificationService(ABC):
    @abstractmethod
    async def verify(self, personal_identity_number: str) -> IntegrationResult:
        pass

class SanctionsCheckService(ABC):
    @abstractmethod
    async def check(self, tax_residency: str, is_pep: bool) -> SanctionsScreening:
        pass

class CreditBureauService(ABC):
    @abstractmethod
    async def evaluate(self, monthly_income: float, monthly_expenses: float, outstanding_debts: float) -> CreditAssessment:
        pass


class RegistryLookupService(ABC):
    @abstractmethod
    async def lookup_entity(self, tax_id: str) -> IntegrationResult:
        pass


class BankAccountValidationService(ABC):
    @abstractmethod
    async def validate_iban(self, iban: str) -> IntegrationResult:
        pass
