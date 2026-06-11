from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any

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