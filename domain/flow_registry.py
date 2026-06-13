from typing import Dict, List, Tuple
from domain.flow import FlowConfig
from flows.sweden_individual import sweden_individual_flow
from flows.sweden_business import sweden_business_flow
from flows.spain_individual import spain_individual_flow
from flows.spain_business import spain_business_flow
from flows.poland_individual import poland_individual_flow
from flows.poland_business import poland_business_flow

class FlowRegistryError(Exception):
    pass

class FlowRegistry:
    def __init__(self):
        self._registry: Dict[Tuple[str, str], FlowConfig] = {}

    def register(self, flow: FlowConfig) -> None:
        key = (flow.country.upper(), flow.account_type.lower())
        self._registry[key] = flow

    def get_flow(self, country: str, account_type: str) -> FlowConfig:
        key = (country.upper(), account_type.lower())
        if key not in self._registry:
            raise FlowRegistryError(
                f"No flow configured for country {country} and account type {account_type}"
            )
        return self._registry[key]

    def all_flows(self) -> List[FlowConfig]:
        return list(self._registry.values())

# Instantiated global lookup registry
flow_registry = FlowRegistry()

# Statically register the supported onboarding journeys.
flow_registry.register(sweden_individual_flow)
flow_registry.register(sweden_business_flow)
flow_registry.register(spain_individual_flow)
flow_registry.register(spain_business_flow)
flow_registry.register(poland_individual_flow)
flow_registry.register(poland_business_flow)
