import pytest

from domain.flow_registry import flow_registry
from web.forms import FormValidationError, validate_step_payload


def test_sweden_identity_rejects_keyboard_smash():
    step = flow_registry.get_flow("SWEDEN", "private").get_step_by_id("collect_identity")

    with pytest.raises(FormValidationError, match="Swedish personal identity number"):
        validate_step_payload(step, "SWEDEN", {"personal_identity_number": "asdfasdf"})


def test_contact_rejects_non_numeric_phone_and_address_without_number():
    step = flow_registry.get_flow("SWEDEN", "private").get_step_by_id("confirm_contact")

    with pytest.raises(FormValidationError, match="Address"):
        validate_step_payload(step, "SWEDEN", {"address": "asdfasdf", "phone_number": "asdfasdf"})

    with pytest.raises(FormValidationError, match="Phone"):
        validate_step_payload(step, "SWEDEN", {"address": "Main Street 12", "phone_number": "asdfasdf"})


def test_select_fields_reject_unknown_tax_residency():
    step = flow_registry.get_flow("SPAIN", "private").get_step_by_id("regulatory_declarations")

    with pytest.raises(FormValidationError, match="Tax Residency"):
        validate_step_payload(step, "SPAIN", {"is_pep": "false", "tax_residency": "banana"})


def test_business_validation_rejects_bad_company_identifier_iban_and_ubo_count():
    identity_step = flow_registry.get_flow("SPAIN", "business").get_step_by_id("business_identity")
    profile_step = flow_registry.get_flow("SPAIN", "business").get_step_by_id("business_profile")
    ubo_step = flow_registry.get_flow("SWEDEN", "business").get_step_by_id("beneficial_owners")

    with pytest.raises(FormValidationError, match="Spanish company NIF"):
        validate_step_payload(
            identity_step,
            "SPAIN",
            {
                "company_identifier": "not-a-nif",
                "legal_name": "Example SL",
                "legal_form": "SL",
                "address": "Calle Mayor 12",
            },
        )

    with pytest.raises(FormValidationError, match="IBAN"):
        validate_step_payload(
            profile_step,
            "SPAIN",
            {
                "sector": "retail",
                "annual_turnover": "100000",
                "expected_monthly_volume": "5000",
                "iban": "not-an-iban",
            },
        )

    with pytest.raises(FormValidationError, match="At least one beneficial owner"):
        validate_step_payload(
            ubo_step,
            "SWEDEN",
            {
                "ubo_count": "0",
                "largest_ownership_percent": "50",
            },
        )
