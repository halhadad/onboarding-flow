import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in [
            "request_id",
            "application_id",
            "component",
            "outcome",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "step_id",
            "country",
            "account_type",
        ]:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = logging.getLogger("onboarding.audit")

class SecurityAuditLogger:
    @staticmethod
    def log_state_mutation(application_id: str, element: str, status_outcome: str, request_id: str) -> None:
        logger.info(
            "state_mutation",
            extra={
                "application_id": application_id,
                "component": element,
                "outcome": status_outcome,
                "request_id": request_id,
            },
        )

    @staticmethod
    def log_integration_check(application_id: str, service_name: str, status_outcome: str, request_id: str) -> None:
        logger.info(
            "integration_check",
            extra={
                "application_id": application_id,
                "component": service_name,
                "outcome": status_outcome,
                "request_id": request_id,
            },
        )
