import json

from services.redaction import redact_integration_payload


def test_integration_payload_redacts_emitted_sensitive_keys():
    payload = redact_integration_payload(
        json.dumps(
            {
                "score": 780,
                "disposable_income": 3200,
                "matched_country": "IR",
                "outcome": "APPROVED",
            }
        )
    )

    result = json.loads(payload)
    assert result["disposable_income"] == "[REDACTED]"
    assert result["matched_country"] == "[REDACTED]"
    assert result["score"] == 780
    assert result["outcome"] == "APPROVED"


def test_integration_payload_redacts_nested_and_listed_sensitive_fields():
    payload = redact_integration_payload(
        json.dumps(
            {
                "status": "COMPLETED",
                "applicant_profile": {
                    "personal_identity_number": "199001011234",
                    "disposable_income": 45000,
                    "city": "Stockholm",
                },
                "accounts": [{"iban": "SE1234"}],
            }
        )
    )

    result = json.loads(payload)
    assert result["status"] == "COMPLETED"
    assert result["applicant_profile"]["personal_identity_number"] == "[REDACTED]"
    assert result["applicant_profile"]["disposable_income"] == "[REDACTED]"
    assert result["applicant_profile"]["city"] == "Stockholm"
    assert result["accounts"][0]["iban"] == "[REDACTED]"
