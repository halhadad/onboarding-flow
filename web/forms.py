import re
from typing import Dict, Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from domain.flow import FlowStep


class FormValidationError(ValueError):
    pass

class IdentityForm(BaseModel):
    personal_identity_number: str = Field(..., min_length=1, max_length=30)

    @field_validator("personal_identity_number")
    @classmethod
    def clean_pin(cls, value: str) -> str:
        # Strip structural hyphens or whitespaces standard in user text entry
        return value.replace("-", "").replace(" ", "").strip()

    @classmethod
    async def from_request(cls, request_form: Dict[str, Any]) -> "IdentityForm":
        return cls(personal_identity_number=request_form.get("personal_identity_number", ""))


class ContactForm(BaseModel):
    address: str = Field(..., min_length=5, max_length=255)
    phone_number: str = Field(..., min_length=5, max_length=30)

    @classmethod
    async def from_request(cls, request_form: Dict[str, Any]) -> "ContactForm":
        return cls(
            address=request_form.get("address", ""),
            phone_number=request_form.get("phone_number", "")
        )


class RegulatoryForm(BaseModel):
    is_pep: bool
    tax_residency: str = Field(..., min_length=2, max_length=50)

    @classmethod
    async def from_request(cls, request_form: Dict[str, Any]) -> "RegulatoryForm":
        # Convert checkbox or standard HTML selection strings into a clean boolean value
        raw_pep = request_form.get("is_pep", "false").lower()
        is_pep_bool = raw_pep in ["true", "on", "yes", "1"]
        
        return cls(
            is_pep=is_pep_bool,
            tax_residency=request_form.get("tax_residency", "")
        )


class FinancialForm(BaseModel):
    monthly_income: float = Field(..., ge=0)
    monthly_expenses: float = Field(..., ge=0)
    outstanding_debts: float = Field(..., ge=0)

    @classmethod
    async def from_request(cls, request_form: Dict[str, Any]) -> "FinancialForm":
        # Handle empty string inputs gracefully by casting them safely to zero
        def safe_float(val: Any) -> float:
            if not val or str(val).strip() == "":
                return 0.0
            try:
                return float(val)
            except ValueError:
                raise ValueError("Value must be a valid numerical figure.")

        return cls(
            monthly_income=safe_float(request_form.get("monthly_income")),
            monthly_expenses=safe_float(request_form.get("monthly_expenses")),
            outstanding_debts=safe_float(request_form.get("outstanding_debts"))
        )


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _validate_identity(country: str, value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    if country.upper() == "SWEDEN":
        if not re.fullmatch(r"(\d{10}|\d{12})", compact):
            raise FormValidationError("Swedish personal identity number must be YYMMDDXXXX or YYYYMMDDXXXX.")
    elif country.upper() == "SPAIN":
        if not re.fullmatch(r"([XYZ]\d{7}[A-Z]|\d{8}[A-Z])", compact):
            raise FormValidationError("Spanish DNI/NIE must look like 12345678Z or X1234567L.")
    elif country.upper() == "POLAND":
        if not re.fullmatch(r"\d{11}", compact):
            raise FormValidationError("Polish PESEL must contain exactly 11 digits.")
    elif not re.fullmatch(r"[A-Z0-9]{6,20}", compact):
        raise FormValidationError("Identity reference has an unsupported format.")
    return compact


def _validate_company_identifier(country: str, value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    if country.upper() == "SWEDEN":
        valid = re.fullmatch(r"\d{10}", compact)
        message = "Swedish organisation number must contain 10 digits."
    elif country.upper() == "SPAIN":
        valid = re.fullmatch(r"[A-Z]\d{7}[A-Z0-9]", compact)
        message = "Spanish company NIF must look like B12345678."
    else:
        valid = re.fullmatch(r"\d{10}|\d{9}|\d{14}", compact)
        message = "Polish company identifier must be a NIP, REGON or KRS-style numeric identifier."
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


def _validate_number(field_name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise FormValidationError(f"{field_name.replace('_', ' ').title()} must be a valid number.") from err
    if number < 0:
        raise FormValidationError(f"{field_name.replace('_', ' ').title()} cannot be negative.")
    if field_name == "largest_ownership_percent" and number > 100:
        raise FormValidationError("Largest ownership percent cannot exceed 100.")
    if field_name == "ubo_count" and number < 1:
        raise FormValidationError("At least one beneficial owner must be supplied.")
    return number


def validate_step_payload(step: FlowStep, country: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for field in step.fields:
        raw_value = form_data.get(field.field_name)
        if field.field_type == "boolean":
            boolean_value = _clean_text(raw_value).lower() in {"true", "on", "yes", "1"}
            if field.requires_true and not boolean_value:
                raise FormValidationError(f"{field.field_name.replace('_', ' ').title()} must be confirmed.")
            clean[field.field_name] = boolean_value
            continue

        text_value = _clean_text(raw_value)
        if field.is_required and not text_value:
            raise FormValidationError(f"{field.field_name.replace('_', ' ').title()} is required.")

        if field.field_type == "number":
            clean[field.field_name] = _validate_number(field.field_name, raw_value)
        elif field.field_type == "select":
            allowed = {option.upper() for option in field.options}
            selected = text_value.upper()
            if selected not in allowed:
                raise FormValidationError(
                    f"{field.field_name.replace('_', ' ').title()} must be one of: {', '.join(field.options)}."
                )
            clean[field.field_name] = selected
        elif field.field_name in {"personal_identity_number", "representative_id"}:
            clean[field.field_name] = _validate_identity(country, text_value)
        elif field.field_name == "company_identifier":
            clean[field.field_name] = _validate_company_identifier(country, text_value)
        elif field.field_name == "phone_number":
            clean[field.field_name] = _validate_phone(text_value)
        elif field.field_name == "iban":
            clean[field.field_name] = _validate_iban(text_value)
        elif field.field_name == "address":
            if len(text_value) < 8 or not re.search(r"\d", text_value):
                raise FormValidationError("Address must include a street or building number.")
            clean[field.field_name] = text_value
        elif field.field_name in {"legal_name", "representative_name"}:
            if not re.fullmatch(r"[A-Za-zÀ-ž0-9 .,'&-]{2,120}", text_value):
                raise FormValidationError(f"{field.field_name.replace('_', ' ').title()} contains unsupported characters.")
            clean[field.field_name] = text_value
        elif field.field_name == "province":
            if not re.fullmatch(r"[A-Za-zÀ-ž .'-]{2,80}", text_value):
                raise FormValidationError("Province must contain a valid province name.")
            clean[field.field_name] = text_value
        else:
            if len(text_value) < 2:
                raise FormValidationError(f"{field.field_name.replace('_', ' ').title()} is too short.")
            clean[field.field_name] = text_value
    return clean
