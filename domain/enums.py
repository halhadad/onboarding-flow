from enum import Enum


class Country(str, Enum):
    """Markets the bank operates onboarding in (not the same as tax residency,
    which can be any country — see domain/countries.py)."""
    SWEDEN = "SWEDEN"
    SPAIN = "SPAIN"
    POLAND = "POLAND"


class AccountType(str, Enum):
    PRIVATE = "private"
    BUSINESS = "business"


class IntegrationName(str, Enum):
    """The external checks a flow step can require. The runner maps each of
    these to a handler, so a typo'd step config fails loudly instead of silently."""
    IDENTITY = "identity"
    ADDRESS_LOOKUP = "address_lookup"
    SANCTIONS = "sanctions"
    CREDIT_BUREAU = "credit_bureau"
    REGISTRY = "registry"
    REPRESENTATIVE = "representative"
    UBO_KYC = "ubo_kyc"
    BUSINESS_CREDIT = "business_credit"
    BANK_ACCOUNT = "bank_account"


class PiiCategory(str, Enum):
    """Redaction category attached to a sensitive field in its flow definition."""
    NATIONAL_ID = "NATIONAL_ID"
    COMPANY_ID = "COMPANY_ID"
    IBAN = "IBAN"
    ADDRESS = "ADDRESS"
    PHONE = "PHONE"
    TAX_RESIDENCY = "TAX_RESIDENCY"


class Sector(str, Enum):
    RETAIL = "retail"
    SERVICES = "services"
    MANUFACTURING = "manufacturing"
    FINANCIAL_SERVICES = "financial_services"
