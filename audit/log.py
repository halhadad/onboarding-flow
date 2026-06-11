import json
import logging
import datetime

logger = logging.getLogger("banking_audit")
logging.basicConfig(level=logging.INFO)

class SecurityAuditLogger:
    @staticmethod
    def log_state_mutation(application_id: str, element: str, status_outcome: str, request_id: str) -> None:
        payload = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "application_id": application_id,
            "component": element,
            "outcome": status_outcome,
            "request_id": request_id
        }
        logger.info(f"[AUDIT_MUTATION] {json.dumps(payload)}")