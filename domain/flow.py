from dataclasses import dataclass, field
from typing import Optional, Sequence

from domain.fields import FieldId, FieldSpec, field_spec

@dataclass(frozen=True)
class FormFieldConfig:
    field_id: FieldId
    is_required: bool = True
    requires_true: bool = False
    # Override the catalog options when a select varies by market (e.g. legal_form).
    options_override: Optional[Sequence[str]] = None

    @property
    def spec(self) -> FieldSpec:
        return field_spec(self.field_id)

    @property
    def field_name(self) -> str:
        return self.spec.key.value

    @property
    def field_type(self) -> str:
        return self.spec.field_type.value

    @property
    def options(self) -> Sequence[str]:
        return tuple(self.options_override) if self.options_override is not None else self.spec.options

    @property
    def is_sensitive(self) -> bool:
        return self.spec.sensitive

    @property
    def display_label(self) -> str:
        return self.spec.label

@dataclass(frozen=True)
class FlowStep:
    step_id: str
    title: str
    description: str
    fields: Sequence[FormFieldConfig]
    required_integrations: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "required_integrations", tuple(self.required_integrations))

@dataclass(frozen=True)
class FlowConfig:
    country: str
    account_type: str
    steps: Sequence[FlowStep]

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))

    def get_step_by_id(self, step_id: str) -> Optional[FlowStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_next_step_id(self, current_step_id: str) -> Optional[str]:
        for i, step in enumerate(self.steps):
            if step.step_id == current_step_id:
                if i + 1 < len(self.steps):
                    return self.steps[i + 1].step_id
                return None
        return None
