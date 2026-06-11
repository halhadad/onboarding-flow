import pytest

from domain.flow_registry import flow_registry


@pytest.mark.parametrize(
    ("country", "account_type"),
    [
        ("SWEDEN", "private"),
        ("SWEDEN", "business"),
        ("SPAIN", "private"),
        ("SPAIN", "business"),
        ("POLAND", "private"),
        ("POLAND", "business"),
    ],
)
def test_all_required_flows_are_registered(country, account_type):
    flow = flow_registry.get_flow(country, account_type)

    assert flow.country == country
    assert flow.account_type == account_type
    assert len(flow.steps) >= 4
