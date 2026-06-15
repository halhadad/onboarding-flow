import re
from typing import Any, Dict

from domain.flow import FlowStep, FormFieldConfig
from domain.enums import Country
from domain.fields import FieldId, FieldType
from web.exceptions import FormValidationError


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


_IDENTITY_PATTERNS: Dict[str, tuple] = {
    Country.SWEDEN: (r"(\d{10}|\d{12})",        "Swedish personal identity number must be YYMMDDXXXX or YYYYMMDDXXXX."),
    Country.SPAIN:  (r"([XYZ]\d{7}[A-Z]|\d{8}[A-Z])", "Spanish DNI/NIE must look like 12345678Z or X1234567L."),
    Country.POLAND: (r"\d{11}",                  "Polish PESEL must contain exactly 11 digits."),
}
_IDENTITY_DEFAULT = (r"[A-Z0-9]{6,20}", "Identity reference has an unsupported format.")

def _validate_identity(_field: FormFieldConfig, country: str, value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    pattern, message = _IDENTITY_PATTERNS.get(country.upper(), _IDENTITY_DEFAULT)
    if not re.fullmatch(pattern, compact):
        raise FormValidationError(message)
    return compact


_COMPANY_ID_PATTERNS: Dict[str, tuple] = {
    Country.SWEDEN: (r"\d{10}",              "Swedish organisation number must contain 10 digits."),
    Country.SPAIN:  (r"[A-Z]\d{7}[A-Z0-9]", "Spanish company NIF must look like B12345678."),
}
_COMPANY_ID_DEFAULT = (r"\d{10}|\d{9}|\d{14}", "Polish company identifier must be a NIP, REGON or KRS style numeric identifier.")

def _validate_company_identifier(field: FormFieldConfig, country: str, value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    pattern, message = _COMPANY_ID_PATTERNS.get(country.upper(), _COMPANY_ID_DEFAULT)
    if not re.fullmatch(pattern, compact):
        raise FormValidationError(message)
    return compact


def _validate_phone(field: FormFieldConfig, country: str, value: str) -> str:
    normalized = value.replace(" ", "")
    if not re.fullmatch(r"\+?[0-9]{7,15}", normalized):
        raise FormValidationError("Phone number must contain 7 to 15 digits and may start with +.")
    return normalized


def _validate_iban(field: FormFieldConfig, country: str, value: str) -> str:
    compact = value.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        raise FormValidationError("IBAN must start with a country code and check digits, for example ES9121000418450200051332.")
    return compact


def _validate_address(field: FormFieldConfig, country: str, value: str) -> str:
    if len(value) < 8 or not re.search(r"\d", value):
        raise FormValidationError("Address must include a street or building number.")
    return value


def _validate_name(field: FormFieldConfig, country: str, value: str) -> str:
    if not re.fullmatch(r"[A-Za-zÀ-ž0-9 .,'&-]{2,120}", value):
        raise FormValidationError(f"{field.display_label} contains unsupported characters.")
    return value


def _validate_province(field: FormFieldConfig, country: str, value: str) -> str:
    if not re.fullmatch(r"[A-Za-zÀ-ž .'-]{2,80}", value):
        raise FormValidationError("Province must contain a valid province name.")
    return value


_TEXT_VALIDATORS = {
    FieldId.PERSONAL_IDENTITY_NUMBER: _validate_identity,
    FieldId.REPRESENTATIVE_ID:        _validate_identity,
    FieldId.COMPANY_IDENTIFIER:       _validate_company_identifier,
    FieldId.PHONE_NUMBER:             _validate_phone,
    FieldId.IBAN:                     _validate_iban,
    FieldId.ADDRESS:                  _validate_address,
    FieldId.LEGAL_NAME:               _validate_name,
    FieldId.REPRESENTATIVE_NAME:      _validate_name,
    FieldId.PROVINCE:                 _validate_province,
}


def _validate_text(field: FormFieldConfig, country: str, value: str) -> str:
    validator = _TEXT_VALIDATORS.get(field.field_id)
    if validator:
        return validator(field, country, value)
    if len(value) < 2:
        raise FormValidationError(f"{field.display_label} is too short.")
    return value


def _validate_number(field: FormFieldConfig, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise FormValidationError(f"{field.display_label} must be a valid number.") from err
    if number < 0:
        raise FormValidationError(f"{field.display_label} cannot be negative.")
    if field.field_id == FieldId.LARGEST_OWNERSHIP_PERCENT and number > 100:
        raise FormValidationError("Largest ownership percent cannot exceed 100.")
    if field.field_id == FieldId.UBO_COUNT and number < 1:
        raise FormValidationError("At least one beneficial owner must be supplied.")
    return number


def validate_step_payload(step: FlowStep, country: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for field in step.fields:
        raw_value = form_data.get(field.field_name)

        if field.field_type == FieldType.BOOLEAN.value:
            boolean_value = _clean_text(raw_value).lower() in {"true", "on", "yes", "1"}
            if field.requires_true and not boolean_value:
                raise FormValidationError(f"{field.display_label} must be confirmed.")
            clean[field.field_name] = boolean_value
            continue

        text_value = _clean_text(raw_value)
        if field.is_required and not text_value:
            raise FormValidationError(f"{field.display_label} is required.")

        if field.field_type == FieldType.NUMBER.value:
            clean[field.field_name] = _validate_number(field, raw_value)
        elif field.field_type == FieldType.SELECT.value:
            allowed = {option.upper() for option in field.options}
            if text_value.upper() not in allowed:
                raise FormValidationError(
                    f"{field.display_label} must be one of: {', '.join(field.options)}."
                )
            clean[field.field_name] = text_value.upper()
        else:
            clean[field.field_name] = _validate_text(field, country, text_value)
    return clean
