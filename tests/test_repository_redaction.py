import json

from services.pii import redact_integration_payload


def test_integration_payload_redacts_sensitive_keys():
    payload = redact_integration_payload(
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


def test_integration_payload_redacts_nested_and_listed_sensitive_fields():
    # A real provider can bury PII inside nested objects/lists; the redaction
    # must walk the whole structure, not just the root keys.
    payload = redact_integration_payload(
        json.dumps(
            {
                "status": "COMPLETED",
                "applicant_profile": {
                    "personal_identity_number": "199001011234",
                    "monthly_income": 45000,
                    "city": "Stockholm",
                },
                "accounts": [{"iban": "SE1234"}],
            }
        )
    )

    result = json.loads(payload)
    assert result["status"] == "COMPLETED"
    assert result["applicant_profile"]["personal_identity_number"] == "***"
    assert result["applicant_profile"]["monthly_income"] == "***"
    assert result["applicant_profile"]["city"] == "Stockholm"
    assert result["accounts"][0]["iban"] == "***"
