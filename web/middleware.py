import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from domain.enums import AuditField

logger = logging.getLogger("onboarding.request")

class BankingSecurityAuditMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        # Give every request a unique audit ID.
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "request_failed",
                extra={
                    AuditField.REQUEST_ID.value: request.state.request_id,
                    AuditField.METHOD.value: request.method,
                    AuditField.PATH.value: request.url.path,
                    AuditField.DURATION_MS.value: duration_ms,
                },
            )
            raise
        
        response.headers["X-Request-ID"] = request.state.request_id
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "request_completed",
            extra={
                AuditField.REQUEST_ID.value: request.state.request_id,
                AuditField.METHOD.value: request.method,
                AuditField.PATH.value: request.url.path,
                AuditField.STATUS_CODE.value: response.status_code,
                AuditField.DURATION_MS.value: duration_ms,
            },
        )
        return response
