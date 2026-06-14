import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from domain.enums import AuditField


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in AuditField:
            if hasattr(record, field.value):
                payload[field.value] = getattr(record, field.value)
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
                AuditField.APPLICATION_ID.value: application_id,
                AuditField.COMPONENT.value: element,
                AuditField.OUTCOME.value: status_outcome,
                AuditField.REQUEST_ID.value: request_id,
            },
        )

    @staticmethod
    def log_integration_check(application_id: str, service_name: str, status_outcome: str, request_id: str) -> None:
        logger.info(
            "integration_check",
            extra={
                AuditField.APPLICATION_ID.value: application_id,
                AuditField.COMPONENT.value: service_name,
                AuditField.OUTCOME.value: status_outcome,
                AuditField.REQUEST_ID.value: request_id,
            },
        )
