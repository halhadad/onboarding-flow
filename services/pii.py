import json
from functools import lru_cache
from typing import Any, Dict, Set

from domain.flow_registry import flow_registry

# Stored application data is kept as entered; only audit logs are redacted.
# Provider response keys carrying financial figures or identifiers; the form
# schema does not describe these, so this set complements the schema field names.
_PROVIDER_SIGNAL_KEYS: Set[str] = {
    "income", "expenses", "debts",
    "monthly_income", "monthly_expenses", "outstanding_debts",
    "annual_turnover", "expected_monthly_volume", "disposable_income",
    "tax_residency", "matched_country", "country_code",
}


@lru_cache(maxsize=1)
def pii_field_categories() -> Dict[str, str]:
    """Map of field name to redaction category, built from every flow."""
    categories: Dict[str, str] = {}
    for flow in flow_registry.all_flows():
        for step in flow.steps:
            for field in step.fields:
                if field.pii_category:
                    categories[field.field_name] = field.pii_category.value
    return categories


@lru_cache(maxsize=1)
def sensitive_log_keys() -> frozenset:
    """Every key whose value must be masked before it reaches a log/audit record."""
    return frozenset(pii_field_categories().keys() | _PROVIDER_SIGNAL_KEYS)


def _deep_redact(data: Any) -> Any:
    """Recursively mask sensitive keys at any depth in dicts/lists."""
    keys = sensitive_log_keys()
    if isinstance(data, dict):
        return {key: ("***" if key in keys else _deep_redact(value)) for key, value in data.items()}
    if isinstance(data, list):
        return [_deep_redact(item) for item in data]
    return data


def redact_integration_payload(response_json: str) -> str:
    """Redact a provider response (at any nesting depth) before it is logged."""
    try:
        payload = json.loads(response_json)
    except (ValueError, TypeError):
        return "{}"
    return json.dumps(_deep_redact(payload), sort_keys=True)
