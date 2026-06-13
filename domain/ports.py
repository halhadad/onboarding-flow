from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from domain.states import CheckOutcome

@dataclass(frozen=True)
class IntegrationResult:
    status_outcome: CheckOutcome
    raw_response_json: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_outcome", CheckOutcome(self.status_outcome))

class ApplicationRepository(ABC):

    @abstractmethod
    def create_application(self, application_id: str, country: str, account_type: str, request_id: str) -> None:
        """Initializes a new application record in the system."""
        pass

    @abstractmethod
    def get_application_status(self, application_id: str) -> Optional[str]:
        """Retrieves the current status string of an application."""
        pass

    @abstractmethod
    def get_application_version(self, application_id: str) -> Optional[int]:
        """Retrieves the current optimistic concurrency version of an application."""
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


class IdentityVerificationService(ABC):
    @abstractmethod
    def verify(self, personal_identity_number: str) -> IntegrationResult:
        """Executes a country-specific identity or national registry check verification."""
        pass

class SanctionsCheckService(ABC):
    @abstractmethod
    def check(self, tax_residency: str, is_pep: bool) -> IntegrationResult:
        """Executes compliance, tax residency, and Politically Exposed Person validations."""
        pass

class CreditBureauService(ABC):
    @abstractmethod
    def evaluate(self, monthly_income: float, monthly_expenses: float, outstanding_debts: float) -> IntegrationResult:
        """Evaluates financial risk profile parameters and affordability logic."""
        pass


class RegistryLookupService(ABC):
    @abstractmethod
    def lookup_entity(self, tax_id: str) -> IntegrationResult:
        """Looks up a legal entity in a mocked business registry."""
        pass


class BankAccountValidationService(ABC):
    @abstractmethod
    def validate_iban(self, iban: str) -> IntegrationResult:
        """Validates a bank account identifier against a mocked bank service."""
        pass
