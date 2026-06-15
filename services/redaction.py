import json
from functools import lru_cache
from typing import Any, FrozenSet

from domain.fields import sensitive_field_keys

_PROVIDER_SIGNAL_KEYS: FrozenSet[str] = frozenset({
    "disposable_income",
    "matched_country",
})

_MASK = "[REDACTED]"


@lru_cache(maxsize=1)
def sensitive_log_keys() -> FrozenSet[str]:
    return sensitive_field_keys() | _PROVIDER_SIGNAL_KEYS


def _deep_redact(data: Any, keys: FrozenSet[str]) -> Any:
    if isinstance(data, dict):
        return {key: (_MASK if key in keys else _deep_redact(value, keys)) for key, value in data.items()}
    if isinstance(data, list):
        return [_deep_redact(item, keys) for item in data]
    return data


def redact_integration_payload(response_json: str) -> str:
    try:
        payload = json.loads(response_json)
    except (ValueError, TypeError):
        return "{}"
    return json.dumps(_deep_redact(payload, sensitive_log_keys()), sort_keys=True)
