from dataclasses import dataclass, field
from typing import Optional, Sequence

@dataclass(frozen=True)
class FormFieldConfig:
    field_name: str
    field_type: str  # text, number, select, boolean
    is_required: bool
    options: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))

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
