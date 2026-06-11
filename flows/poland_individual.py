from domain.flow import FlowConfig, FlowStep, FormFieldConfig


poland_individual_flow = FlowConfig(
    country="POLAND",
    account_type="private",
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="PESEL Verification",
            description="Enter your PESEL so we can run an eID-style identity mock.",
            fields=[
                FormFieldConfig("personal_identity_number", "text", True),
            ],
            required_integrations=["identity"],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact and Registered Address",
            description="Confirm your phone number and registered address.",
            fields=[
                FormFieldConfig("address", "text", True),
                FormFieldConfig("phone_number", "text", True),
            ],
            required_integrations=["address_lookup"],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Regulatory Declarations",
            description="Confirm PEP status, sanctions declaration and tax residency.",
            fields=[
                FormFieldConfig("is_pep", "boolean", True),
                FormFieldConfig("tax_residency", "select", True, ["PL", "SE", "ES"]),
            ],
            required_integrations=["sanctions"],
        ),
        FlowStep(
            step_id="financial_profile",
            title="BIK-style Affordability",
            description="Provide income and affordability information for the credit mock.",
            fields=[
                FormFieldConfig("monthly_income", "number", True),
                FormFieldConfig("monthly_expenses", "number", True),
                FormFieldConfig("outstanding_debts", "number", True),
            ],
            required_integrations=["credit_bureau"],
        ),
    ],
)
