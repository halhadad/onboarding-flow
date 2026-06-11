from typing import Dict, Tuple
from domain.flow import FlowConfig
from flows.sweden_individual import sweden_individual_flow

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

# Instantiated global lookup registry
flow_registry = FlowRegistry()

# Statically register the Swedish private journey
flow_registry.register(sweden_individual_flow)