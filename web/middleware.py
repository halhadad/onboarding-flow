import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class BankingSecurityAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Ensure every request has a unique audit trail ID
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        response = await call_next(request)
        
        # Attach the audit ID to the response headers for observability
        response.headers["X-Request-ID"] = request.state.request_id
        return response