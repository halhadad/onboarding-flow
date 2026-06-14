import uuid
from datetime import datetime, timezone


def new_uuid() -> str:
    """A new random UUID string."""
    return str(uuid.uuid4())


def now_utc() -> datetime:
    """Current time, UTC aware."""
    return datetime.now(timezone.utc)
