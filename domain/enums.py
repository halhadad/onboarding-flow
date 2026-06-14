from enum import Enum


class Country(str, Enum):
    """Markets the bank onboards in."""
    SWEDEN = "SWEDEN"
    SPAIN = "SPAIN"
    POLAND = "POLAND"


class AccountType(str, Enum):
    PRIVATE = "private"
    BUSINESS = "business"


class IntegrationName(str, Enum):
    """External checks a step can require."""
    IDENTITY = "identity"
    ADDRESS_LOOKUP = "address_lookup"
    SANCTIONS = "sanctions"
    CREDIT_BUREAU = "credit_bureau"
    REGISTRY = "registry"
    REPRESENTATIVE = "representative"
    UBO_KYC = "ubo_kyc"
    BUSINESS_CREDIT = "business_credit"
    BANK_ACCOUNT = "bank_account"


class Sector(str, Enum):
    RETAIL = "retail"
    SERVICES = "services"
    MANUFACTURING = "manufacturing"
    FINANCIAL_SERVICES = "financial_services"


class IdentityStatus(str, Enum):
    """Verdict reported by the identity provider."""
    VERIFIED = "verified"
    EXPIRED_ID = "expired_id"
    AMBIGUOUS = "ambiguous_match"


class RegistryStatus(str, Enum):
    """Verdict reported by the company registry."""
    ACTIVE = "active_company"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous_company_match"


class BankAccountStatus(str, Enum):
    """Verdict reported by the bank account check."""
    VERIFIED = "iban_verified"
    NAME_MISMATCH = "name_mismatch"


class DebtFlag(str, Enum):
    """Affordability flags raised by the credit bureau."""
    NEGATIVE_SURPLUS = "NEGATIVE_SURPLUS"
    HIGH_LEVERAGE_RISK = "HIGH_LEVERAGE_RISK"


class AuditField(str, Enum):
    """Structured log keys; single source for producers and the JSON line."""
    REQUEST_ID = "request_id"
    APPLICATION_ID = "application_id"
    COMPONENT = "component"
    OUTCOME = "outcome"
    METHOD = "method"
    PATH = "path"
    STATUS_CODE = "status_code"
    DURATION_MS = "duration_ms"
