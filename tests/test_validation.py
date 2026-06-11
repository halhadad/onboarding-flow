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
