class StateTransitionError(Exception):
    """An application was asked to make an illegal state change."""


class FlowRegistryError(Exception):
    """No flow is configured for a country and account type."""


class ResumeApplicationError(Exception):
    """An application cannot be resumed."""
