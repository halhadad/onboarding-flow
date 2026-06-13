from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

from main import app
from web.dependencies import get_application_repository


class WebRouteSecurityRepository:
    def __init__(self, status: str = "STARTED", country: str = "SWEDEN", account_type: str = "private"):
        self.context = {
            "id": "app-1",
            "country": country,
            "account_type": account_type,
            "status": status,
            "version": 1,
        }
        self.responses: Dict[tuple[str, str], Dict[str, Any]] = {}

    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        return self.context if application_id == "app-1" else None

    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        if resume_token == "valid-token":
            return {**self.context, "resume_token_expired": False}
        return None

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        return self.responses.get((application_id, step_id))


def _client_with_repository(repository: WebRouteSecurityRepository) -> TestClient:
    app.dependency_overrides[get_application_repository] = lambda: repository
    return TestClient(app)


def test_step_route_rejects_terminal_application_direct_url():
    client = _client_with_repository(WebRouteSecurityRepository(status="APPROVED"))
    try:
        response = client.get("/application/app-1/step/collect_identity?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_step_route_rejects_query_country_tampering():
    client = _client_with_repository(WebRouteSecurityRepository(country="SWEDEN", account_type="private"))
    client.cookies.set("bank_onboarding_resume", "valid-token")
    try:
        response = client.get("/application/app-1/step/collect_identity?country=SPAIN&type=private")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_step_route_rejects_opening_later_step_before_previous_steps():
    client = _client_with_repository(WebRouteSecurityRepository())
    client.cookies.set("bank_onboarding_resume", "valid-token")
    try:
        response = client.get("/application/app-1/step/financial_profile?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_step_route_allows_first_incomplete_step_for_active_application():
    repository = WebRouteSecurityRepository(status="IN_PROGRESS")
    repository.responses[("app-1", "collect_identity")] = {"form_data": {}, "payload_hash": "h1"}
    client = _client_with_repository(repository)
    client.cookies.set("bank_onboarding_resume", "valid-token")
    try:
        response = client.get("/application/app-1/step/confirm_contact?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Contact Details" in response.text


def test_step_route_rejects_active_application_without_resume_cookie():
    client = _client_with_repository(WebRouteSecurityRepository(status="IN_PROGRESS"))
    try:
        response = client.get("/application/app-1/step/collect_identity?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
