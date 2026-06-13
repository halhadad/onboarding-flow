from integrations.identity import MockIdentityVerificationService


def test_identity_mock_does_not_reject_normal_year_2000_identifier():
    service = MockIdentityVerificationService()

    result = service.verify("200001011234")

    assert result.status_outcome == "APPROVED"


def test_identity_mock_uses_last_four_digits_as_deterministic_sentinels():
    service = MockIdentityVerificationService()

    assert service.verify("199001010000").status_outcome == "REJECTED"
    assert service.verify("199001011111").status_outcome == "MANUAL_REVIEW"
