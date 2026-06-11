import json

from repositories.application_repo import SQLAlchemyApplicationRepository


def test_step_response_redacts_direct_identifiers():
    repository = SQLAlchemyApplicationRepository(session=None)

    redacted = repository._redact_form_data(
        {
            "personal_identity_number": "199001011234",
            "address": "Main Street 12",
            "phone_number": "+46701234567",
            "monthly_income": 5000,
        }
    )

    assert redacted["personal_identity_number"] == "***1234"
    assert redacted["address"] == "***t 12"
    assert redacted["phone_number"] == "***4567"
    assert redacted["monthly_income"] == 5000


def test_integration_payload_redacts_sensitive_fields():
    repository = SQLAlchemyApplicationRepository(session=None)

    payload = repository._redact_integration_payload(
        json.dumps(
            {
                "income": 5000,
                "expenses": 2000,
                "tax_residency": "SE",
                "outcome": "APPROVED",
            }
        )
    )

    assert json.loads(payload) == {
        "expenses": "***",
        "income": "***",
        "outcome": "APPROVED",
        "tax_residency": "***",
    }
