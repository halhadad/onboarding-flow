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

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_outcome", CheckOutcome(self.status_outcome))

class ApplicationRepository(ABC):

    @abstractmethod
    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> str:
        """Create a new application; return its resume token."""
        pass

    @abstractmethod
    def get_application_status(self, application_id: str) -> Optional[str]:
        """Retrieves the current status string of an application."""
        pass

    @abstractmethod
    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves non-sensitive application routing and status metadata."""
        pass

    @abstractmethod
    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        """Retrieves application routing metadata by a non-ID resume token."""
        pass

    @abstractmethod
    def update_application_status(self, application_id: str, status: str, current_version: int) -> None:
        """Updates the application status utilizing optimistic concurrency control."""
        pass

    @abstractmethod
    def save_step_response(self, application_id: str, step_id: str, form_data: Dict[str, Any], payload_hash: str) -> None:
        """Saves or overwrites a step form payload atomically to guarantee step-level idempotency."""
        pass

    @abstractmethod
    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a previously saved step response payload."""
        pass

    @abstractmethod
    def log_integration_check(self, application_id: str, service_name: str, status_outcome: CheckOutcome, response_json: str, request_id: str) -> None:
        """Appends an execution log record to the immutable audit ledger."""
        pass

    @abstractmethod
    def save_decision(self, application_id: str, outcome: str, reasons: list) -> None:
        """Records (or replaces) the final automated decision and its reasons."""
        pass

    @abstractmethod
    def atomic(self) -> AbstractContextManager[None]:
        """Unit of work: commit on success, roll back on any error."""
        pass


class IdentityVerificationService(ABC):
    @abstractmethod
    async def verify(self, personal_identity_number: str) -> IntegrationResult:
        """Identity provider check (async, network bound)."""
        pass

class SanctionsCheckService(ABC):
    @abstractmethod
    async def check(self, tax_residency: str, is_pep: bool) -> SanctionsScreening:
        """Sanctions / PEP screening signals (async, network bound)."""
        pass

class CreditBureauService(ABC):
    @abstractmethod
    async def evaluate(self, monthly_income: float, monthly_expenses: float, outstanding_debts: float) -> CreditAssessment:
        """Raw affordability signals (async, network bound)."""
        pass


class RegistryLookupService(ABC):
    @abstractmethod
    async def lookup_entity(self, tax_id: str) -> IntegrationResult:
        """Company registry lookup (async, network bound)."""
        pass


class BankAccountValidationService(ABC):
    @abstractmethod
    async def validate_iban(self, iban: str) -> IntegrationResult:
        """Bank account check (async, network bound)."""
        pass
