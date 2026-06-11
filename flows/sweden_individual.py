from domain.flow import FlowConfig, FlowStep, FormFieldConfig

sweden_individual_flow = FlowConfig(
    country="SWEDEN",
    account_type="private",
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="Identity Verification",
            description="Please enter your Swedish personal identity number to initiate verification via BankID.",
            fields=[
                FormFieldConfig(
                    field_name="personal_identity_number",
                    field_type="text",
                    is_required=True
                )
            ],
            required_integrations=["identity"]
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact Details",
            description="Verify your current residential address and telephone information.",
            fields=[
                FormFieldConfig(
                    field_name="address",
                    field_type="text",
                    is_required=True
                ),
                FormFieldConfig(
                    field_name="phone_number",
                    field_type="text",
                    is_required=True
                )
            ],
            required_integrations=["address_lookup"]
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Regulatory Declarations",
            description="Provide necessary compliance, tax residency, and Politically Exposed Person status declarations.",
            fields=[
                FormFieldConfig(
                    field_name="is_pep",
                    field_type="boolean",
                    is_required=True
                ),
                FormFieldConfig(
                    field_name="tax_residency",
                    field_type="select",
                    is_required=True,
                    options=["SE", "ES", "PL"]
                )
            ],
            required_integrations=["sanctions"]
        ),
        FlowStep(
            step_id="financial_profile",
            title="Financial Profile",
            description="Please provide details regarding your monthly employment income, expenses, and outstanding liabilities.",
            fields=[
                FormFieldConfig(
                    field_name="monthly_income",
                    field_type="number",
                    is_required=True
                ),
                FormFieldConfig(
                    field_name="monthly_expenses",
                    field_type="number",
                    is_required=True
                ),
                FormFieldConfig(
                    field_name="outstanding_debts",
                    field_type="number",
                    is_required=True
                )
            ],
            required_integrations=["credit_bureau"]
        )
    ]
)
