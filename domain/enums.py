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


class PiiCategory(str, Enum):
    """Redaction category for a sensitive field."""
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
