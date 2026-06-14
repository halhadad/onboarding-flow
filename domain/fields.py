from dataclasses import dataclass
from enum import Enum
from typing import Dict, Sequence

from domain.enums import Sector


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    BOOLEAN = "boolean"


class FieldId(str, Enum):
    PERSONAL_IDENTITY_NUMBER = "personal_identity_number"
    REPRESENTATIVE_ID = "representative_id"
    COMPANY_IDENTIFIER = "company_identifier"
    REPRESENTATIVE_NAME = "representative_name"
    LEGAL_NAME = "legal_name"
    LEGAL_FORM = "legal_form"
    ADDRESS = "address"
    PROVINCE = "province"
    PHONE_NUMBER = "phone_number"
    IBAN = "iban"
    TAX_RESIDENCY = "tax_residency"
    SECTOR = "sector"
    IS_PEP = "is_pep"
    HAS_SIGNATORY_AUTHORITY = "has_signatory_authority"
    MONTHLY_INCOME = "monthly_income"
    MONTHLY_EXPENSES = "monthly_expenses"
    OUTSTANDING_DEBTS = "outstanding_debts"
    ANNUAL_TURNOVER = "annual_turnover"
    EXPECTED_MONTHLY_VOLUME = "expected_monthly_volume"
    UBO_COUNT = "ubo_count"
    LARGEST_OWNERSHIP_PERCENT = "largest_ownership_percent"
    CONSENT = "consent"


# Legal forms vary by market; the option sets stay in the domain layer.
LEGAL_FORMS_SWEDEN = ("AB", "HB", "Enskild firma")
LEGAL_FORMS_SPAIN = ("SL", "SA", "Autonomo")
LEGAL_FORMS_POLAND = ("Sp. z o.o.", "SA", "CEIDG")

_SECTOR_OPTIONS = tuple(s.value for s in Sector)

# Tax residency is a person attribute, not one of the three markets: a representative
# subset of ISO two letter country codes; sanctioned ones included so the reject path
# is reachable (the screening policy itself lives in config.SANCTIONED_RESIDENCIES).
TAX_RESIDENCY_OPTIONS = (
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES",
    "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LT",
    "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI",
    "SK", "US", "CA", "AU",
    "IR", "KP", "SY",
)


@dataclass(frozen=True)
class FieldSpec:
    key: FieldId
    field_type: FieldType
    label: str
    sensitive: bool = True  # secure by default; opt out only for non sensitive fields
    options: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))


def _spec(key: FieldId, field_type: FieldType, label: str, sensitive: bool = True, options: Sequence[str] = ()) -> FieldSpec:
    return FieldSpec(key=key, field_type=field_type, label=label, sensitive=sensitive, options=options)


# Declared once. Anything not explicitly cleared as public stays sensitive.
FIELD_CATALOG: Dict[FieldId, FieldSpec] = {
    spec.key: spec
    for spec in (
        _spec(FieldId.PERSONAL_IDENTITY_NUMBER, FieldType.TEXT, "Personal identity number"),
        _spec(FieldId.REPRESENTATIVE_ID, FieldType.TEXT, "Representative ID"),
        _spec(FieldId.COMPANY_IDENTIFIER, FieldType.TEXT, "Company identifier"),
        _spec(FieldId.REPRESENTATIVE_NAME, FieldType.TEXT, "Representative name"),
        _spec(FieldId.LEGAL_NAME, FieldType.TEXT, "Legal name"),
        _spec(FieldId.LEGAL_FORM, FieldType.SELECT, "Legal form", sensitive=False),
        _spec(FieldId.ADDRESS, FieldType.TEXT, "Address"),
        _spec(FieldId.PROVINCE, FieldType.TEXT, "Province"),
        _spec(FieldId.PHONE_NUMBER, FieldType.TEXT, "Phone number"),
        _spec(FieldId.IBAN, FieldType.TEXT, "IBAN"),
        _spec(FieldId.TAX_RESIDENCY, FieldType.SELECT, "Tax residency", options=TAX_RESIDENCY_OPTIONS),
        _spec(FieldId.SECTOR, FieldType.SELECT, "Sector", sensitive=False, options=_SECTOR_OPTIONS),
        _spec(FieldId.IS_PEP, FieldType.BOOLEAN, "Politically Exposed Person (PEP)", sensitive=False),
        _spec(FieldId.HAS_SIGNATORY_AUTHORITY, FieldType.BOOLEAN, "Signatory authority", sensitive=False),
        _spec(FieldId.MONTHLY_INCOME, FieldType.NUMBER, "Monthly income"),
        _spec(FieldId.MONTHLY_EXPENSES, FieldType.NUMBER, "Monthly expenses"),
        _spec(FieldId.OUTSTANDING_DEBTS, FieldType.NUMBER, "Outstanding debts"),
        _spec(FieldId.ANNUAL_TURNOVER, FieldType.NUMBER, "Annual turnover"),
        _spec(FieldId.EXPECTED_MONTHLY_VOLUME, FieldType.NUMBER, "Expected monthly volume"),
        _spec(FieldId.UBO_COUNT, FieldType.NUMBER, "Number of beneficial owners", sensitive=False),
        _spec(FieldId.LARGEST_OWNERSHIP_PERCENT, FieldType.NUMBER, "Largest ownership (%)", sensitive=False),
        _spec(FieldId.CONSENT, FieldType.BOOLEAN, "I confirm the information provided is accurate and I consent to the processing of my data for the purposes of this application.", sensitive=False),
    )
}


def field_spec(key: FieldId) -> FieldSpec:
    return FIELD_CATALOG[key]


def sensitive_field_keys() -> frozenset:
    return frozenset(spec.key.value for spec in FIELD_CATALOG.values() if spec.sensitive)


