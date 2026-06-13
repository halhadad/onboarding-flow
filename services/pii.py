"""Keeping personal data out of the audit/operational logs.

Design decision: the captured application data itself (in `step_responses`) is
stored **as entered**, not redacted. A bank legitimately needs to read those
answers later (support, review, compliance), so destroying them would be wrong.
The production answer for protecting them at rest is encryption + access control
+ retention policy (see README), not redaction.

What we *do* redact is anything written to the **audit trail / logs**, because
those are for "what happened", not for holding raw identifiers. That redaction
is driven by the same flow schema (`FormFieldConfig.pii_category`) plus the
known financial signal keys, and it walks nested structures so a sensitive value
buried inside an object cannot leak.
"""

import json
from functools import lru_cache
from typing import Any, Dict, Set

from domain.flow_registry import flow_registry

# Keys that appear in provider responses and carry raw financial figures or
# identifiers. Provider payloads are not described by the form schema, so this
# small set complements the schema-derived field names below.
_PROVIDER_SIGNAL_KEYS: Set[str] = {
    "income", "expenses", "debts",
    "monthly_income", "monthly_expenses", "outstanding_debts",
    "annual_turnover", "expected_monthly_volume", "disposable_income",
    "tax_residency", "matched_country", "country_code",
}


@lru_cache(maxsize=1)
def pii_field_categories() -> Dict[str, str]:
    """Map of {form_field_name: redaction_category} built from every flow.

    Single source of truth for which fields are sensitive — also what a
    production system would drive field-level encryption from.
    """
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
