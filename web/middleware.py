import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("onboarding.request")

class BankingSecurityAuditMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and log each request."""

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
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        
        # Attach the audit ID to the response headers for observability
        response.headers["X-Request-ID"] = request.state.request_id
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "request_completed",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
