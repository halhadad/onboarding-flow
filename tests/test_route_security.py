from typing import Any, Dict, Optional

import pytest
from fastapi import HTTPException

from domain.flow_registry import flow_registry
from web.views import _assert_step_can_be_rendered, _load_routable_application_context


class RouteSecurityRepository:
    def __init__(self, context: Optional[Dict[str, Any]]):
        self.context = context
        self.responses: Dict[tuple[str, str], Dict[str, Any]] = {}

    def get_application_context(self, application_id: str) -> Optional[Dict[str, Any]]:
        return self.context

    def get_application_context_by_resume_token(self, resume_token: str) -> Optional[Dict[str, Any]]:
        if resume_token == "valid-token" and self.context:
            return {**self.context, "resume_token_expired": False}
        if resume_token == "expired-token" and self.context:
            return {**self.context, "resume_token_expired": True}
        return None

    def get_step_response(self, application_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        return self.responses.get((application_id, step_id))


def _context(status: str = "STARTED") -> Dict[str, Any]:
    return {
        "id": "app-1",
        "country": "SWEDEN",
        "account_type": "private",
        "status": status,
        "version": 1,
    }


def test_route_guard_rejects_missing_application():
    repository = RouteSecurityRepository(context=None)

    with pytest.raises(HTTPException) as exc_info:
        _load_routable_application_context(repository, "app-1", "SWEDEN", "private", "valid-token")

    assert exc_info.value.status_code == 404


def test_route_guard_rejects_country_or_type_tampering():
    repository = RouteSecurityRepository(context=_context())

    with pytest.raises(HTTPException) as country_exc:
        _load_routable_application_context(repository, "app-1", "SPAIN", "private", "valid-token")

    with pytest.raises(HTTPException) as type_exc:
        _load_routable_application_context(repository, "app-1", "SWEDEN", "business", "valid-token")

    assert country_exc.value.status_code == 403
    assert type_exc.value.status_code == 403


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED", "MANUAL_REVIEW"])
def test_route_guard_rejects_terminal_applications(status):
    repository = RouteSecurityRepository(context=_context(status=status))

    with pytest.raises(HTTPException) as exc_info:
        _load_routable_application_context(repository, "app-1", "SWEDEN", "private")

    assert exc_info.value.status_code == 409


def test_route_guard_allows_active_matching_application():
    repository = RouteSecurityRepository(context=_context(status="IN_PROGRESS"))

    context = _load_routable_application_context(repository, "app-1", "sweden", "PRIVATE", "valid-token")

    assert context["id"] == "app-1"


def test_route_guard_rejects_active_application_without_matching_resume_cookie():
    repository = RouteSecurityRepository(context=_context(status="IN_PROGRESS"))

    with pytest.raises(HTTPException) as missing_cookie_exc:
        _load_routable_application_context(repository, "app-1", "SWEDEN", "private")

    with pytest.raises(HTTPException) as bad_cookie_exc:
        _load_routable_application_context(repository, "app-1", "SWEDEN", "private", "wrong-token")

    with pytest.raises(HTTPException) as expired_cookie_exc:
        _load_routable_application_context(repository, "app-1", "SWEDEN", "private", "expired-token")

    assert missing_cookie_exc.value.status_code == 403
    assert bad_cookie_exc.value.status_code == 403
    assert expired_cookie_exc.value.status_code == 403


def test_render_guard_rejects_opening_later_step_before_previous_steps():
    repository = RouteSecurityRepository(context=_context())
    flow = flow_registry.get_flow("SWEDEN", "private")

    with pytest.raises(HTTPException) as exc_info:
        _assert_step_can_be_rendered(flow, repository, "app-1", "financial_profile")

    assert exc_info.value.status_code == 403


def test_render_guard_allows_first_incomplete_step():
    repository = RouteSecurityRepository(context=_context())
    repository.responses[("app-1", "collect_identity")] = {"form_data": {}, "payload_hash": "h1"}
    flow = flow_registry.get_flow("SWEDEN", "private")

    _assert_step_can_be_rendered(flow, repository, "app-1", "confirm_contact")
