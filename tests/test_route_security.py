"""
Route security tests at two levels:
- Unit: call the guard functions directly with a stub repository
- HTTP: hit the full stack via TestClient to prove the guards wire up end-to-end
"""
from typing import Any, Dict, Optional

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from domain.flow_registry import flow_registry
from main import app
from web.dependencies import get_application_repository
from web.views import _assert_step_can_be_rendered, _load_routable_application_context


# ---------------------------------------------------------------------------
# Shared stub repository
# ---------------------------------------------------------------------------

class StubRepository:
    _SENTINEL = object()

    def __init__(
        self,
        context: Any = _SENTINEL,
        *,
        status: str = "STARTED",
        country: str = "SWEDEN",
        account_type: str = "private",
    ):
        self.context = context if context is not self._SENTINEL else {
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
        if resume_token == "valid-token" and self.context:
            return {**self.context, "resume_token_expired": False}
        if resume_token == "expired-token" and self.context:
            return {**self.context, "resume_token_expired": True}
        return None

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        return self.responses.get((application_id, step_id))


def _http_client(repository: StubRepository) -> TestClient:
    app.dependency_overrides[get_application_repository] = lambda: repository
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit-level guard tests (_load_routable_application_context)
# ---------------------------------------------------------------------------

def test_guard_rejects_missing_application():
    repo = StubRepository(context=None)
    with pytest.raises(HTTPException) as exc:
        _load_routable_application_context(repo, "app-1", "SWEDEN", "private", "valid-token")
    assert exc.value.status_code == 404


def test_guard_rejects_country_or_type_tampering():
    repo = StubRepository()
    with pytest.raises(HTTPException) as country_exc:
        _load_routable_application_context(repo, "app-1", "SPAIN", "private", "valid-token")
    with pytest.raises(HTTPException) as type_exc:
        _load_routable_application_context(repo, "app-1", "SWEDEN", "business", "valid-token")
    assert country_exc.value.status_code == 403
    assert type_exc.value.status_code == 403


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED", "MANUAL_REVIEW"])
def test_guard_rejects_terminal_applications(status: str):
    repo = StubRepository(status=status)
    with pytest.raises(HTTPException) as exc:
        _load_routable_application_context(repo, "app-1", "SWEDEN", "private")
    assert exc.value.status_code == 409


def test_guard_allows_active_matching_application():
    repo = StubRepository(status="IN_PROGRESS")
    context = _load_routable_application_context(repo, "app-1", "sweden", "PRIVATE", "valid-token")
    assert context["id"] == "app-1"


def test_guard_rejects_missing_expired_and_wrong_resume_cookie():
    repo = StubRepository(status="IN_PROGRESS")
    for token in [None, "wrong-token", "expired-token"]:
        with pytest.raises(HTTPException) as exc:
            _load_routable_application_context(repo, "app-1", "SWEDEN", "private", token)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Unit-level render guard tests (_assert_step_can_be_rendered)
# ---------------------------------------------------------------------------

def test_render_guard_rejects_later_step_without_prior_responses():
    repo = StubRepository()
    flow = flow_registry.get_flow("SWEDEN", "private")
    with pytest.raises(HTTPException) as exc:
        _assert_step_can_be_rendered(flow, repo, "app-1", "financial_profile")
    assert exc.value.status_code == 403


def test_render_guard_allows_next_incomplete_step():
    repo = StubRepository()
    repo.responses[("app-1", "collect_identity")] = {"form_data": {}, "payload_hash": "h1"}
    flow = flow_registry.get_flow("SWEDEN", "private")
    _assert_step_can_be_rendered(flow, repo, "app-1", "confirm_contact")


# ---------------------------------------------------------------------------
# HTTP-level tests (full stack via TestClient)
# ---------------------------------------------------------------------------

def test_http_rejects_terminal_application_direct_url():
    client = _http_client(StubRepository(status="APPROVED"))
    try:
        response = client.get("/application/app-1/step/collect_identity?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409


def test_http_rejects_country_tampering_in_query():
    repo = StubRepository()
    client = _http_client(repo)
    client.cookies.set("bank_onboarding_resume", "valid-token")
    try:
        response = client.get("/application/app-1/step/collect_identity?country=SPAIN&type=private")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_http_rejects_later_step_without_prior_responses():
    client = _http_client(StubRepository())
    client.cookies.set("bank_onboarding_resume", "valid-token")
    try:
        response = client.get("/application/app-1/step/financial_profile?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_http_allows_next_step_when_prior_step_complete():
    repo = StubRepository(status="IN_PROGRESS")
    repo.responses[("app-1", "collect_identity")] = {"form_data": {}, "payload_hash": "h1"}
    client = _http_client(repo)
    client.cookies.set("bank_onboarding_resume", "valid-token")
    try:
        response = client.get("/application/app-1/step/confirm_contact?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Contact Details" in response.text


def test_http_rejects_active_application_without_resume_cookie():
    client = _http_client(StubRepository(status="IN_PROGRESS"))
    try:
        response = client.get("/application/app-1/step/collect_identity?country=SWEDEN&type=private")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
