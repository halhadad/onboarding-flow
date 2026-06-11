from domain.flow import FlowConfig, FlowStep, FormFieldConfig


spain_business_flow = FlowConfig(
    country="SPAIN",
    account_type="business",
    steps=[
        FlowStep(
            step_id="business_identity",
            title="Company NIF and Legal Form",
            description="Enter company NIF, legal form and registered address.",
            fields=[
                FormFieldConfig("company_identifier", "text", True),
                FormFieldConfig("legal_name", "text", True),
                FormFieldConfig("legal_form", "select", True, ["SL", "SA", "Autonomo"]),
                FormFieldConfig("address", "text", True),
            ],
            required_integrations=["registry"],
        ),
        FlowStep(
            step_id="representative",
            title="Legal Representative",
            description="Verify representative identity and authority.",
            fields=[
                FormFieldConfig("representative_name", "text", True),
                FormFieldConfig("representative_id", "text", True),
                FormFieldConfig("has_signatory_authority", "boolean", True),
            ],
            required_integrations=["identity", "representative"],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Ownership",
            description="Capture beneficial owners and ownership percentages.",
            fields=[
                FormFieldConfig("ubo_count", "number", True),
                FormFieldConfig("largest_ownership_percent", "number", True),
            ],
            required_integrations=["ubo_kyc", "sanctions"],
        ),
        FlowStep(
            step_id="business_profile",
            title="KYB and Bank Account",
            description="Provide sector, turnover, tax details and expected usage.",
            fields=[
                FormFieldConfig("sector", "select", True, ["retail", "services", "manufacturing", "financial_services"]),
                FormFieldConfig("annual_turnover", "number", True),
                FormFieldConfig("expected_monthly_volume", "number", True),
                FormFieldConfig("iban", "text", True),
            ],
            required_integrations=["business_credit", "bank_account"],
        ),
    ],
)
