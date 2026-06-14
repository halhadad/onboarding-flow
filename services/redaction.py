import json
from functools import lru_cache
from typing import Any, FrozenSet

from domain.fields import sensitive_field_keys

# Stored application data is kept as entered; only audit logs are redacted.
# Extra keys our provider payloads emit that are not captured form fields
# (production would use path-aware redaction rather than bare key names).
_PROVIDER_SIGNAL_KEYS: FrozenSet[str] = frozenset({
    "disposable_income",
    "matched_country",
})

_MASK = "[REDACTED]"


@lru_cache(maxsize=1)
def sensitive_log_keys() -> FrozenSet[str]:
    """Every key whose value must be masked before it reaches a log/audit record."""
    return sensitive_field_keys() | _PROVIDER_SIGNAL_KEYS


def _deep_redact(data: Any, keys: FrozenSet[str]) -> Any:
    """Mask sensitive keys at any depth; value type is irrelevant."""
    if isinstance(data, dict):
        return {key: (_MASK if key in keys else _deep_redact(value, keys)) for key, value in data.items()}
    if isinstance(data, list):
        return [_deep_redact(item, keys) for item in data]
    return data


def redact_integration_payload(response_json: str) -> str:
    """Redact a provider response (at any nesting depth) before it is logged."""
    try:
        payload = json.loads(response_json)
    except (ValueError, TypeError):
        return "{}"
    return json.dumps(_deep_redact(payload, sensitive_log_keys()), sort_keys=True)
