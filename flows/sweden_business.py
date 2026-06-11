from domain.flow import FlowConfig, FlowStep, FormFieldConfig


sweden_business_flow = FlowConfig(
    country="SWEDEN",
    account_type="business",
    steps=[
        FlowStep(
            step_id="business_identity",
            title="Company Details",
            description="Enter organisation number, legal name and legal form.",
            fields=[
                FormFieldConfig("company_identifier", "text", True),
                FormFieldConfig("legal_name", "text", True),
                FormFieldConfig("legal_form", "select", True, ["AB", "HB", "Enskild firma"]),
            ],
            required_integrations=["registry"],
        ),
        FlowStep(
            step_id="representative",
            title="Authorised Representative",
            description="Confirm the representative and signatory authority.",
            fields=[
                FormFieldConfig("representative_name", "text", True),
                FormFieldConfig("representative_id", "text", True),
                FormFieldConfig("has_signatory_authority", "boolean", True),
            ],
            required_integrations=["representative"],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Owners",
            description="Capture beneficial owner count and highest ownership percentage.",
            fields=[
                FormFieldConfig("ubo_count", "number", True),
                FormFieldConfig("largest_ownership_percent", "number", True),
            ],
            required_integrations=["ubo_kyc", "sanctions"],
        ),
        FlowStep(
            step_id="business_profile",
            title="Business Activity",
            description="Provide business activity, turnover and expected usage.",
            fields=[
                FormFieldConfig("sector", "select", True, ["retail", "services", "manufacturing", "financial_services"]),
                FormFieldConfig("annual_turnover", "number", True),
                FormFieldConfig("expected_monthly_volume", "number", True),
            ],
            required_integrations=["business_credit"],
        ),
    ],
)
