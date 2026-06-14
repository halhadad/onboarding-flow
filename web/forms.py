import re
from typing import Any, Callable, Dict

from domain.flow import FlowStep, FormFieldConfig
from domain.enums import Country
from domain.fields import FieldId
from web.exceptions import FormValidationError


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _validate_identity(country: str, value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    market = country.upper()
    if market == Country.SWEDEN:
        if not re.fullmatch(r"(\d{10}|\d{12})", compact):
            raise FormValidationError("Swedish personal identity number must be YYMMDDXXXX or YYYYMMDDXXXX.")
    elif market == Country.SPAIN:
        if not re.fullmatch(r"([XYZ]\d{7}[A-Z]|\d{8}[A-Z])", compact):
            raise FormValidationError("Spanish DNI/NIE must look like 12345678Z or X1234567L.")
    elif market == Country.POLAND:
        if not re.fullmatch(r"\d{11}", compact):
            raise FormValidationError("Polish PESEL must contain exactly 11 digits.")
    elif not re.fullmatch(r"[A-Z0-9]{6,20}", compact):
        raise FormValidationError("Identity reference has an unsupported format.")
    return compact


def _validate_company_identifier(country: str, value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    market = country.upper()
    if market == Country.SWEDEN:
        valid = re.fullmatch(r"\d{10}", compact)
        message = "Swedish organisation number must contain 10 digits."
    elif market == Country.SPAIN:
        valid = re.fullmatch(r"[A-Z]\d{7}[A-Z0-9]", compact)
        message = "Spanish company NIF must look like B12345678."
    else:
        valid = re.fullmatch(r"\d{10}|\d{9}|\d{14}", compact)
        message = "Polish company identifier must be a NIP, REGON or KRS style numeric identifier."
    if not valid:
        raise FormValidationError(message)
    return compact


def _validate_phone(value: str) -> str:
    normalized = value.replace(" ", "")
    if not re.fullmatch(r"\+?[0-9]{7,15}", normalized):
        raise FormValidationError("Phone number must contain 7 to 15 digits and may start with +.")
    return normalized


def _validate_iban(value: str) -> str:
    compact = value.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        raise FormValidationError("IBAN must start with a country code and check digits, for example ES9121000418450200051332.")
    return compact


def _validate_address(value: str) -> str:
    if len(value) < 8 or not re.search(r"\d", value):
        raise FormValidationError("Address must include a street or building number.")
    return value


def _validate_name(field: FormFieldConfig, value: str) -> str:
    if not re.fullmatch(r"[A-Za-zÀ-ž0-9 .,'&-]{2,120}", value):
        raise FormValidationError(f"{field.display_label} contains unsupported characters.")
    return value


def _validate_province(value: str) -> str:
    if not re.fullmatch(r"[A-Za-zÀ-ž .'-]{2,80}", value):
        raise FormValidationError("Province must contain a valid province name.")
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


_TEXT_VALIDATORS: Dict[FieldId, Callable[[FormFieldConfig, str, str], str]] = {
    FieldId.PERSONAL_IDENTITY_NUMBER: lambda field, country, value: _validate_identity(country, value),
    FieldId.REPRESENTATIVE_ID: lambda field, country, value: _validate_identity(country, value),
    FieldId.COMPANY_IDENTIFIER: lambda field, country, value: _validate_company_identifier(country, value),
    FieldId.PHONE_NUMBER: lambda field, country, value: _validate_phone(value),
    FieldId.IBAN: lambda field, country, value: _validate_iban(value),
    FieldId.ADDRESS: lambda field, country, value: _validate_address(value),
    FieldId.LEGAL_NAME: lambda field, country, value: _validate_name(field, value),
    FieldId.REPRESENTATIVE_NAME: lambda field, country, value: _validate_name(field, value),
    FieldId.PROVINCE: lambda field, country, value: _validate_province(value),
}


def _validate_text(field: FormFieldConfig, country: str, value: str) -> str:
    validator = _TEXT_VALIDATORS.get(field.field_id)
    if validator:
        return validator(field, country, value)
    if len(value) < 2:
        raise FormValidationError(f"{field.display_label} is too short.")
    return value


def validate_step_payload(step: FlowStep, country: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for field in step.fields:
        raw_value = form_data.get(field.field_name)

        if field.field_type == "boolean":
            boolean_value = _clean_text(raw_value).lower() in {"true", "on", "yes", "1"}
            if field.requires_true and not boolean_value:
                raise FormValidationError(f"{field.display_label} must be confirmed.")
            clean[field.field_name] = boolean_value
            continue

        text_value = _clean_text(raw_value)
        if field.is_required and not text_value:
            raise FormValidationError(f"{field.display_label} is required.")

        if field.field_type == "number":
            clean[field.field_name] = _validate_number(field, raw_value)
        elif field.field_type == "select":
            allowed = {option.upper() for option in field.options}
            if text_value.upper() not in allowed:
                raise FormValidationError(
                    f"{field.display_label} must be one of: {', '.join(field.options)}."
                )
            clean[field.field_name] = text_value.upper()
        else:
            clean[field.field_name] = _validate_text(field, country, text_value)
    return clean
